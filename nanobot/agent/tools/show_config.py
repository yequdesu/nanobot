
"""Tools for showing prompt and configuration files."""

from pathlib import Path
from typing import Any

from nanobot.agent.tools.base import Tool


class ShowPromptTool(Tool):
    """Show current system prompt."""
    
    def __init__(self, context_builder: Any = None):
        self._context_builder = context_builder
    
    @property
    def name(self) -> str:
        return "show_prompt"
    
    @property
    def description(self) -> str:
        return "Show the current system prompt being used by the agent. Returns the complete system prompt including identity, skills, and memory context."
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
    
    async def execute(self, **kwargs: Any) -> str:
        """Return the current system prompt."""
        if self._context_builder is None:
            return "Error: Context builder not initialized"
        
        try:
            system_prompt = self._context_builder.build_system_prompt()
            
            # 添加元信息
            header = f"# System Prompt\n\n**Total Length:** {len(system_prompt)} characters\n\n"
            
            # 如果提示词太长，添加截断说明
            if len(system_prompt) > 8000:
                content = system_prompt[:8000]
                footer = f"\n\n... [Truncated, {len(system_prompt) - 8000} more characters]"
                return header + "```markdown\n" + content + footer + "\n```"
            
            return header + "```markdown\n" + system_prompt + "\n```"
        except Exception as e:
            return f"Error building system prompt: {str(e)}"


class ShowSoulTool(Tool):
    """Show SOUL.md content."""
    
    def __init__(self, workspace: Path = None):
        self._workspace = workspace
    
    @property
    def name(self) -> str:
        return "show_soul"
    
    @property
    def description(self) -> str:
        return "Show the content of SOUL.md file from the workspace. This file defines the agent's personality and values."
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
    
    async def execute(self, **kwargs: Any) -> str:
        """Return SOUL.md content."""
        if self._workspace is None:
            return "Error: Workspace not initialized"
        
        soul_file = self._workspace / "SOUL.md"
        
        if not soul_file.exists():
            return "SOUL.md not found in workspace."
        
        try:
            content = soul_file.read_text(encoding="utf-8")
            header = f"# SOUL.md\n\n**Location:** {soul_file}\n\n"
            return header + "```markdown\n" + content + "\n```"
        except Exception as e:
            return f"Error reading SOUL.md: {str(e)}"


class ShowIdentityTool(Tool):
    """Show IDENTITY.md content."""
    
    def __init__(self, workspace: Path = None):
        self._workspace = workspace
    
    @property
    def name(self) -> str:
        return "show_identity"
    
    @property
    def description(self) -> str:
        return "Show the content of IDENTITY.md file from the workspace. This file defines the agent's core identity and capabilities."
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
    
    async def execute(self, **kwargs: Any) -> str:
        """Return IDENTITY.md content."""
        if self._workspace is None:
            return "Error: Workspace not initialized"
        
        identity_file = self._workspace / "IDENTITY.md"
        
        if not identity_file.exists():
            return "IDENTITY.md not found in workspace."
        
        try:
            content = identity_file.read_text(encoding="utf-8")
            header = f"# IDENTITY.md\n\n**Location:** {identity_file}\n\n"
            return header + "```markdown\n" + content + "\n```"
        except Exception as e:
            return f"Error reading IDENTITY.md: {str(e)}"


class ShowAgentsTool(Tool):
    """Show AGENTS.md content."""
    
    def __init__(self, workspace: Path = None):
        self._workspace = workspace
    
    @property
    def name(self) -> str:
        return "show_agents"
    
    @property
    def description(self) -> str:
        return "Show the content of AGENTS.md file from the workspace. This file contains agent instructions and guidelines."
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
    
    async def execute(self, **kwargs: Any) -> str:
        """Return AGENTS.md content."""
        if self._workspace is None:
            return "Error: Workspace not initialized"
        
        agents_file = self._workspace / "AGENTS.md"
        
        if not agents_file.exists():
            return "AGENTS.md not found in workspace."
        
        try:
            content = agents_file.read_text(encoding="utf-8")
            header = f"# AGENTS.md\n\n**Location:** {agents_file}\n\n"
            return header + "```markdown\n" + content + "\n```"
        except Exception as e:
            return f"Error reading AGENTS.md: {str(e)}"
