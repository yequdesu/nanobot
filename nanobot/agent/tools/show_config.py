"""Tools for showing prompt and configuration files."""

from pathlib import Path
from typing import Any

from nanobot.agent.tools.base import BaseTool


class ShowPromptTool(BaseTool):
    """Show current system prompt."""
    
    name = "show_prompt"
    description = "Show the current system prompt being used by the agent. Returns the complete system prompt including identity, skills, and memory context."
    parameters = {
        "type": "object",
        "properties": {},
        "required": []
    }
    
    def __init__(self, context_builder: Any = None):
        self.context_builder = context_builder
    
    async def execute(self, **kwargs) -> str:
        """Return the current system prompt."""
        if self.context_builder is None:
            return "Error: Context builder not initialized"
        
        try:
            system_prompt = self.context_builder.build_system_prompt()
            
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


class ShowSoulTool(BaseTool):
    """Show SOUL.md content."""
    
    name = "show_soul"
    description = "Show the content of SOUL.md file from the workspace. This file defines the agent's personality and values."
    parameters = {
        "type": "object",
        "properties": {},
        "required": []
    }
    
    def __init__(self, workspace: Path = None):
        self.workspace = workspace
    
    async def execute(self, **kwargs) -> str:
        """Return SOUL.md content."""
        if self.workspace is None:
            return "Error: Workspace not initialized"
        
        soul_file = self.workspace / "SOUL.md"
        
        if not soul_file.exists():
            return "SOUL.md not found in workspace."
        
        try:
            content = soul_file.read_text(encoding="utf-8")
            header = f"# SOUL.md\n\n**Location:** {soul_file}\n\n"
            return header + "```markdown\n" + content + "\n```"
        except Exception as e:
            return f"Error reading SOUL.md: {str(e)}"


class ShowIdentityTool(BaseTool):
    """Show IDENTITY.md content."""
    
    name = "show_identity"
    description = "Show the content of IDENTITY.md file from the workspace. This file defines the agent's core identity and capabilities."
    parameters = {
        "type": "object",
        "properties": {},
        "required": []
    }
    
    def __init__(self, workspace: Path = None):
        self.workspace = workspace
    
    async def execute(self, **kwargs) -> str:
        """Return IDENTITY.md content."""
        if self.workspace is None:
            return "Error: Workspace not initialized"
        
        identity_file = self.workspace / "IDENTITY.md"
        
        if not identity_file.exists():
            return "IDENTITY.md not found in workspace."
        
        try:
            content = identity_file.read_text(encoding="utf-8")
            header = f"# IDENTITY.md\n\n**Location:** {identity_file}\n\n"
            return header + "```markdown\n" + content + "\n```"
        except Exception as e:
            return f"Error reading IDENTITY.md: {str(e)}"


class ShowAgentsTool(BaseTool):
    """Show AGENTS.md content."""
    
    name = "show_agents"
    description = "Show the content of AGENTS.md file from the workspace. This file contains agent instructions and guidelines."
    parameters = {
        "type": "object",
        "properties": {},
        "required": []
    }
    
    def __init__(self, workspace: Path = None):
        self.workspace = workspace
    
    async def execute(self, **kwargs) -> str:
        """Return AGENTS.md content."""
        if self.workspace is None:
            return "Error: Workspace not initialized"
        
        agents_file = self.workspace / "AGENTS.md"
        
        if not agents_file.exists():
            return "AGENTS.md not found in workspace."
        
        try:
            content = agents_file.read_text(encoding="utf-8")
            header = f"# AGENTS.md\n\n**Location:** {agents_file}\n\n"
            return header + "```markdown\n" + content + "\n```"
        except Exception as e:
            return f"Error reading AGENTS.md: {str(e)}"
