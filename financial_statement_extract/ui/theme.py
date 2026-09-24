"""Semantic workspace tokens and native-control styles.

The legacy theme remains available for compatibility with existing callers.
"""

from dataclasses import dataclass
import tkinter as tk
from tkinter import font, ttk
from types import MappingProxyType

WINDOW_TITLE = "Financial Statement Extract"
WINDOW_GEOMETRY = "1120x820"
PLACEHOLDER_FOREGROUND = "#888888"
ENTRY_FOREGROUND = "#000000"

COLORS = MappingProxyType({
    "background": "#F3F5F7",
    "surface": "#FFFFFF",
    "surface-subtle": "#F7F8FA",
    "text-primary": "#202A35",
    "text-muted": "#596775",
    "accent": "#175CD3",
    "accent-hover": "#1249AA",
    "border": "#DCE1E7",
    "selection": "#E6EFFD",
    "selection-text": "#153E78",
    "warning": "#895300",
    "warning-surface": "#FFF5DD",
    "error": "#AE2D36",
    "error-surface": "#FDEDEF",
    "success": "#326447",
    "focus": "#175CD3",
    "disabled-text": "#65717E",
    "disabled-surface": "#E6E9ED",
})
SPACING = MappingProxyType({"xs": 4, "sm": 8, "md": 12, "lg": 20, "xl": 28})
TYPE_SIZES = MappingProxyType({"body": 10, "small": 9, "section": 11, "title": 18, "empty": 17})
CONTROL_HEIGHT = 34
ROW_HEIGHT = 34
SETUP_WIDTH = 280
NARROW_BREAKPOINT = 940
SMALLER_TEXT_BREAKPOINT = 960
SMALLEST_TEXT_BREAKPOINT = 760
RESPONSIVE_TEXT_SCALES = MappingProxyType({"normal": 1.0, "smaller": 0.9, "smallest": 0.8})
MIN_WINDOW_SIZE = (640, 700)
CORNER_RADIUS = "platform-native"


def responsive_text_tier(window_width: int) -> tuple[str, float]:
    """Return the discrete text tier for the current window width."""
    if window_width < SMALLEST_TEXT_BREAKPOINT:
        return "smallest", RESPONSIVE_TEXT_SCALES["smallest"]
    if window_width < SMALLER_TEXT_BREAKPOINT:
        return "smaller", RESPONSIVE_TEXT_SCALES["smaller"]
    return "normal", RESPONSIVE_TEXT_SCALES["normal"]


def _effective_font_size(size: int, text_scale: float, responsive_scale: float) -> int:
    # An explicit enlarged-text preference is an accessibility override and
    # must not be undone merely because the window is narrow.
    window_scale = responsive_scale if text_scale <= 1.0 else 1.0
    return max(1, round(size * text_scale * window_scale))


@dataclass
class WorkspaceTheme:
    """Keep named font objects alive and scale layout with the current display."""

    fonts: dict[str, font.Font]
    scale: float
    text_scale: float
    colors: dict[str, str]
    system_colors: bool
    responsive_text_scale: float = 1.0

    def px(self, value: int) -> int:
        return max(1, round(value * self.scale))

    def space(self, name: str) -> int:
        # Text enlargement must not also double decorative whitespace.
        return max(1, round(SPACING[name] * self.scale / self.text_scale))

    def set_responsive_text_scale(self, scale: float) -> bool:
        """Resize named fonts in place so every existing widget updates."""
        if scale == self.responsive_text_scale:
            return False
        self.responsive_text_scale = scale
        for role, size in TYPE_SIZES.items():
            self.fonts[role].configure(size=_effective_font_size(size, self.text_scale, scale))
        return True


def apply_workspace_theme(root: tk.Tk, *, text_scale: float = 1.0,
                          system_colors: bool = False, theme: WorkspaceTheme | None = None) -> WorkspaceTheme:
    """Style ttk controls, keeping the platform's focus and keyboard behavior."""
    if not 0.75 <= text_scale <= 2.0:
        raise ValueError("Text scale must be between 0.75 and 2.0.")
    style = ttk.Style(root)
    available = style.theme_names()
    # Prefer Windows native controls. On other platforms retain their theme.
    if root.tk.call("tk", "windowingsystem") == "win32":
        for name in ("vista", "xpnative", "winnative"):
            if name in available:
                style.theme_use(name)
                break
    family = font.nametofont("TkDefaultFont", root=root).actual("family")
    responsive_scale = theme.responsive_text_scale if theme is not None else 1.0
    fonts = theme.fonts if theme is not None else {
        role: font.Font(root=root, family=family, size=_effective_font_size(size, text_scale, responsive_scale),
                        weight="bold" if role in {"title", "section", "empty"} else "normal")
        for role, size in TYPE_SIZES.items()
    }
    for role, size in TYPE_SIZES.items():
        fonts[role].configure(size=_effective_font_size(size, text_scale, responsive_scale))
    scale = float(root.tk.call("tk", "scaling")) / (96 / 72) * text_scale
    c = dict(COLORS)
    if system_colors:
        if root.tk.call("tk", "windowingsystem") != "win32":
            raise ValueError("System colors are supported by this workspace on Windows only.")
        c.update({key: "SystemWindow" for key in ("background", "surface", "surface-subtle", "warning-surface", "error-surface")})
        c.update({key: "SystemWindowText" for key in ("text-primary", "text-muted", "warning", "error", "success", "border", "focus")})
        c.update(accent="SystemHighlight", **{"accent-hover": "SystemHighlight", "selection": "SystemHighlight",
                 "selection-text": "SystemHighlightText", "disabled-text": "SystemGrayText", "disabled-surface": "SystemButtonFace"})
    if theme is None:
        theme = WorkspaceTheme(fonts, scale, text_scale, c, system_colors, responsive_scale)
    else:
        theme.scale, theme.text_scale, theme.colors, theme.system_colors = scale, text_scale, c, system_colors
    root.configure(background=c["background"])
    style.configure("Workspace.TFrame", background=c["background"])
    style.configure("Surface.TFrame", background=c["surface"])
    style.configure("Subtle.TFrame", background=c["surface-subtle"])
    for name, role, bg, fg in (
        ("Body", "body", "surface", "text-primary"),
        ("Muted", "small", "surface", "text-muted"),
        ("Section", "section", "surface", "text-primary"),
        ("Title", "title", "background", "text-primary"),
        ("Caption", "small", "background", "text-muted"),
        ("Empty", "empty", "surface", "text-primary"),
        ("Setup", "body", "surface-subtle", "text-primary"),
        ("SetupLabel", "small", "surface-subtle", "text-primary"),
        ("SetupMuted", "small", "surface-subtle", "text-muted"),
        ("SetupTitle", "section", "surface-subtle", "text-primary"),
    ):
        style.configure(f"{name}.TLabel", font=fonts[role], background=c[bg], foreground=c[fg])
    for name, tone, bg in (("Status", "text-muted", "background"), ("Warning", "warning", "warning-surface"),
                           ("Error", "error", "error-surface"), ("Success", "success", "background")):
        style.configure(f"{name}.TLabel", font=fonts["small"], background=c[bg], foreground=c[tone])
    style.configure("Workspace.TButton", font=fonts["body"], padding=(theme.space("md"), theme.space("xs")))
    style.configure("Workspace.TEntry", font=fonts["body"], padding=theme.space("xs"))
    style.configure("Workspace.TCombobox", font=fonts["body"], padding=theme.space("xs"))
    style.configure("Workspace.TNotebook", background=c["surface"])
    style.configure("Workspace.TNotebook.Tab", font=fonts["body"], padding=(theme.space("md"), 1))
    # Native Windows buttons ignore fill colors. Use ttk's built-in clam drawing
    # elements for the single accent button; it is still a keyboard-native ttk.Button.
    for element in ("border", "focus", "padding", "label"):
        target = f"WorkspaceAccent.{element}"
        if target not in style.element_names():
            style.element_create(target, "from", "clam", f"Button.{element}")
    style.layout("Accent.TButton", [("WorkspaceAccent.border", {"sticky": "nswe", "children": [
        ("WorkspaceAccent.focus", {"sticky": "nswe", "children": [
            ("WorkspaceAccent.padding", {"sticky": "nswe", "children": [
                ("WorkspaceAccent.label", {"sticky": "nswe"}),
            ]}),
        ]}),
    ]})])
    style.configure("Accent.TButton", font=fonts["body"], background=c["accent"], foreground=c["surface"],
                    bordercolor=c["accent"], lightcolor=c["accent"], darkcolor=c["accent"],
                    focuscolor=c["surface"], focusthickness=1,
                    padding=(theme.space("lg"), theme.space("sm")), anchor="center")
    style.map("Accent.TButton",
              background=[("disabled", c["disabled-surface"]), ("pressed", c["accent-hover"]),
                          ("active", c["accent-hover"])],
              foreground=[("disabled", c["disabled-text"])],
              bordercolor=[("disabled", c["border"]), ("focus", c["focus"])])
    if system_colors:
        # Native button elements inherit the current Windows contrast scheme.
        style.layout("Accent.TButton", style.layout("TButton"))
        style.configure("Accent.TButton", foreground="SystemButtonText", background="SystemButtonFace",
                        focuscolor="SystemButtonText")
        style.map("Accent.TButton", background=[], foreground=[("disabled", "SystemGrayText")], bordercolor=[])
    style.configure("Workspace.Treeview", font=fonts["body"], rowheight=max(theme.px(ROW_HEIGHT),
                    fonts["body"].metrics("linespace") + theme.space("md")),
                    background=c["surface"], fieldbackground=c["surface"], foreground=c["text-primary"], borderwidth=0)
    style.configure("Workspace.Treeview.Heading", font=fonts["small"], padding=(theme.space("sm"), theme.space("sm")))
    style.map("Workspace.Treeview", background=[("selected", c["selection"])],
              foreground=[("selected", c["selection-text"])])
    style.configure("Workspace.Horizontal.TProgressbar", thickness=theme.px(4))
    root.option_add("*TCombobox*Listbox.font", str(fonts["body"]))
    return theme


def apply_theme(root: tk.Tk) -> None:
    """Retain the existing theme selection and Tk's default if unavailable."""
    try:
        ttk.Style(root).theme_use("clam")
    except tk.TclError:
        pass
