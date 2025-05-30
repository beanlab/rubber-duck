from pathlib import Path
from typing import List, Optional
from ..utils.logger import duck_logger


class FolderUtils:
    def __init__(self):
        self.base_path = Path(__file__).parent.parent.parent / "prompts"

    def get_project_folder(self, project_name: str) -> Path:
        """
        Find the actual project folder that matches the project number.
        Handles cases like "project_3"
        """
        # Convert project name to folder name format (e.g., "Project 1" -> "project_1")
        folder_name = project_name.lower().replace(' ', '_')
        
        # Find all matching project folders
        project_folders = list(self.base_path.glob(f"{folder_name}*"))
        
        if not project_folders:
            duck_logger.error(f"No matching folder found for {folder_name}")
            return None
            
        # Use the first matching folder
        folder_path = project_folders[0]
        duck_logger.debug(f"Found project folder: {folder_path}")
        return folder_path

    def get_text_files(self, folder_name: List[str]) -> Optional[List[str]]:
        """
        Get all .txt files in the project folder.
        Returns None if folder_name is empty or no contents found.
        """
        if not folder_name:
            return None

        folder_path = self.get_project_folder(folder_name[0])
        
        if not folder_path or not folder_path.exists():
            duck_logger.error(f"Folder not found: {folder_path}")
            return None

        try:
            files = [str(f) for f in folder_path.iterdir() if f.is_file() and f.suffix == '.txt']
            duck_logger.debug(f"Found .txt files in {folder_path}: {files}")
            return files
        except Exception as e:
            duck_logger.error(f"Error reading folder contents: {e}")
            return None

    def get_yaml_files(self, folder_name: List[str]) -> Optional[List[str]]:
        """
        Get all .yaml files in the project folder.
        Returns None if folder_name is empty or no contents found.
        """
        if not folder_name:
            return None

        folder_path = self.get_project_folder(folder_name[0])
        
        if not folder_path or not folder_path.exists():
            duck_logger.error(f"Folder not found: {folder_path}")
            return None

        try:
            files = [str(f) for f in folder_path.iterdir() if f.is_file() and f.suffix in ['.yaml', '.yml']]
            duck_logger.debug(f"Found YAML files in {folder_path}: {files}")
            return files
        except Exception as e:
            duck_logger.error(f"Error reading folder contents: {e}")
            return None
