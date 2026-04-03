"""Custom exception hierarchy for CWM."""


class CWMError(Exception):
    """Base exception for all CWM errors."""


class ConfigNotFoundError(CWMError):
    """No .cwm/ directory found in the current or parent directories."""


class WorktreeExistsError(CWMError):
    """A worktree for this branch already exists."""


class WorktreeNotFoundError(CWMError):
    """The named worktree does not exist."""


class NotInSubshellError(CWMError):
    """Command requires being inside a CWM subshell (use 'cwm enter' first)."""


class GitError(CWMError):
    """A git command failed."""


class ColconError(CWMError):
    """A colcon build or invocation failed."""


class UnderlayNotFoundError(CWMError):
    """The specified underlay path does not exist or is invalid."""


class SubRepoNotFoundError(CWMError):
    """The specified sub-repository path does not exist or is not a git repository."""


class MetaModeRequiredError(CWMError):
    """This operation requires a meta-repository workspace (cwm init --meta)."""
