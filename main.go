package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

const usage = `jdisk — SJTU Netdisk CLI (list / download / upload)

Usage:
  jdisk login
        Log in by scanning a QR code with the SJTU mobile app. This is the
        only authentication method.
  jdisk ls [<remote-path>] [-l]
        List a directory (default: root). -l = long format with readable sizes.
  jdisk download <remote-path> [<local-path>]
        Download a file. If local-path is a directory, the file keeps its
        remote name.
  jdisk upload <local-file> [<remote-path>] [--overwrite]
        Upload a file. Default destination is the root directory; a remote
        path ending in '/' is treated as a directory.
`

func main() {
	args := os.Args[1:]
	if len(args) == 0 {
		fmt.Fprint(os.Stderr, usage)
		os.Exit(2)
	}

	var err error
	switch args[0] {
	case "login":
		err = cmdLogin(args[1:])
	case "ls":
		err = cmdList(args[1:])
	case "download":
		err = cmdDownload(args[1:])
	case "upload":
		err = cmdUpload(args[1:])
	case "help", "-h", "--help":
		fmt.Fprint(os.Stdout, usage)
		return
	default:
		fmt.Fprintf(os.Stderr, "jdisk: unknown command %q\n\n%s", args[0], usage)
		os.Exit(2)
	}

	if err != nil {
		fmt.Fprintf(os.Stderr, "jdisk: %v\n", err)
		os.Exit(1)
	}
}

// --- login ---

func cmdLogin(args []string) error {
	fs := flag.NewFlagSet("login", flag.ExitOnError)
	fs.Usage = func() { fmt.Fprintln(os.Stderr, "Usage: jdisk login") }
	fs.Parse(args)
	if fs.NArg() > 0 {
		fs.Usage()
		os.Exit(2)
	}
	_, err := loginWithQR()
	return err
}

func mustSessionPath() string {
	p, err := sessionPath()
	if err != nil {
		return "~/.config/jdisk/session.json"
	}
	return p
}

// --- ls ---

func cmdList(args []string) error {
	fs := flag.NewFlagSet("ls", flag.ExitOnError)
	long := fs.Bool("l", false, "long format with human-readable sizes")
	fs.Usage = func() { fmt.Fprintln(os.Stderr, "Usage: jdisk ls [<remote-path>] [-l]") }
	fs.Parse(args)

	dir := "/"
	if rest := fs.Args(); len(rest) > 0 {
		dir = rest[0]
	}

	sess, err := loadSession()
	if err != nil {
		return fmt.Errorf("not logged in (run `jdisk login` first)")
	}
	client, err := sess.client()
	if err != nil {
		return err
	}
	list, err := client.List(dir)
	if err != nil {
		return err
	}

	entries := append([]Entry(nil), list.Contents...)
	sort.SliceStable(entries, func(i, j int) bool {
		di, dj := entries[i].Type == "dir", entries[j].Type == "dir"
		if di != dj {
			return di // dirs first
		}
		return entries[i].Name < entries[j].Name
	})

	for _, e := range entries {
		if *long {
			kind, size := "-", "-"
			if e.Type == "dir" {
				kind = "d"
			} else {
				size = humanSize(int64(e.Size))
			}
			mod := strings.TrimSuffix(e.ModificationTime, ".000Z")
			if len(mod) > 16 {
				mod = mod[:16]
			}
			fmt.Printf("%s %10s  %s  %s\n", kind, size, mod, e.Name)
		} else {
			if e.Type == "dir" {
				fmt.Printf("%s/\n", e.Name)
			} else {
				fmt.Println(e.Name)
			}
		}
	}
	return nil
}

// --- download ---

func cmdDownload(args []string) error {
	fs := flag.NewFlagSet("download", flag.ExitOnError)
	fs.Usage = func() { fmt.Fprintln(os.Stderr, "Usage: jdisk download <remote-path> [<local-path>]") }
	fs.Parse(args)
	rest := fs.Args()
	if len(rest) < 1 {
		fs.Usage()
		os.Exit(2)
	}
	remote, local := rest[0], ""
	if len(rest) > 1 {
		local = rest[1]
	}
	if local == "" {
		local = fileBase(remote)
	} else if strings.HasSuffix(local, "/") {
		if err := os.MkdirAll(local, 0o755); err != nil {
			return err
		}
		local = filepath.Join(local, fileBase(remote))
	} else if st, err := os.Stat(local); err == nil && st.IsDir() {
		local = filepath.Join(local, fileBase(remote))
	}

	sess, err := loadSession()
	if err != nil {
		return fmt.Errorf("not logged in (run `jdisk login` first)")
	}
	client, err := sess.client()
	if err != nil {
		return err
	}
	prog := newProgress("download")
	n, err := client.Download(remote, local, prog)
	finishProgress()
	if err != nil {
		return err
	}
	fmt.Printf("downloaded %s (%s)\n", local, humanSize(n))
	return nil
}

// --- upload ---

func cmdUpload(args []string) error {
	fs := flag.NewFlagSet("upload", flag.ExitOnError)
	overwrite := fs.Bool("overwrite", false, "overwrite the remote file if it exists")
	fs.Usage = func() { fmt.Fprintln(os.Stderr, "Usage: jdisk upload <local-file> [<remote-path>] [--overwrite]") }
	fs.Parse(args)
	rest := fs.Args()
	if len(rest) < 1 {
		fs.Usage()
		os.Exit(2)
	}
	local := rest[0]
	remote := ""
	if len(rest) > 1 {
		remote = rest[1]
	}
	if remote == "" {
		remote = fileBase(local)
	}

	// Resolve ambiguous targets: if the destination names an existing
	// directory, upload into it (like scp); a trailing '/' forces it.
	if strings.HasSuffix(remote, "/") {
		remote = remote + fileBase(local)
	} else {
		sess, err := loadSession()
		if err != nil {
			return fmt.Errorf("not logged in (run `jdisk login` first)")
		}
		client, err := sess.client()
		if err != nil {
			return err
		}
		parent, name := splitRemote(remote)
		list, err := client.List(parent)
		if err == nil {
			for _, e := range list.Contents {
				if e.Name == name && e.Type == "dir" {
					remote = remote + "/" + fileBase(local)
					break
				}
			}
		}
	}

	sess, err := loadSession()
	if err != nil {
		return fmt.Errorf("not logged in (run `jdisk login` first)")
	}
	client, err := sess.client()
	if err != nil {
		return err
	}
	prog := newProgress("upload")
	err = client.Upload(local, remote, *overwrite, prog)
	finishProgress()
	if err != nil {
		return err
	}
	fmt.Printf("uploaded %s -> %s\n", local, remote)
	return nil
}

// fileBase returns the last segment of a slash-separated path.
func fileBase(p string) string {
	p = strings.TrimRight(p, "/")
	if i := strings.LastIndexByte(p, '/'); i >= 0 {
		return p[i+1:]
	}
	return p
}

// splitRemote splits a remote path into its parent directory and final name.
func splitRemote(p string) (parent, name string) {
	p = strings.Trim(p, "/")
	if i := strings.LastIndexByte(p, '/'); i >= 0 {
		return p[:i], p[i+1:]
	}
	return "", p
}
