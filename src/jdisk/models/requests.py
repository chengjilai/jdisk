"""API request models for SJTU Netdisk API."""

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class UploadInitRequest:
    """Upload initialization request model."""

    part_number_range: List[int]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API request."""
        return {
            "partNumberRange": self.part_number_range,
        }


@dataclass
class UploadConfirmRequest:
    """Upload confirmation request model."""

    confirm_key: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API request."""
        return {
            "confirmKey": self.confirm_key,
        }


@dataclass
class FileMoveRequest:
    """File move request model."""

    to: str
    conflict_resolution_strategy: str = "rename"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API request."""
        return {
            "to": self.to,
            "conflict_resolution_strategy": self.conflict_resolution_strategy,
        }


@dataclass
class BatchMoveRequest:
    """Batch move request model."""

    moves: List[Dict[str, Any]]

    def to_dict(self) -> List[Dict[str, Any]]:
        """Convert to list of dictionaries for API request."""
        return self.moves

    @classmethod
    def create_move_items(cls, from_paths: List[str], to_path: str, file_infos: List[Any]) -> "BatchMoveRequest":
        """Create batch move request from paths and file infos."""
        moves = []
        for from_path, file_info in zip(from_paths, file_infos):
            if not file_info:
                continue

            item_type = "file" if not file_info.is_dir else ""
            to_full_path = f"{to_path.rstrip('/')}/{file_info.name}" if to_path != "/" else f"/{file_info.name}"

            moves.append(
                {
                    "from": from_path,
                    "to": to_full_path,
                    "type": item_type,
                    "conflict_resolution_strategy": "rename",
                    "move_authority": file_info.is_dir,
                }
            )

        return cls(moves=moves)
