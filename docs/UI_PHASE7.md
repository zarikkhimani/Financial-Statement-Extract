# UI Phase 7: keyboard access, text size, and overflow

Run `run.bat` for the live workspace. This pass changes presentation and navigation,
not extraction decisions, page-review policy, workbook contents, or file-open policy.

## Design

The frontend skill's app guidance shaped this pass: a calm, cardless results surface,
short operational labels, and one primary action. Content order remains filing and
output context, optional setup, results/recovery, and status. Interactions are native
keyboard traversal, immediate state-preserving disclosures, and scroll-to-focus;
there is no new decorative animation.

The setup restore control and primary-action/status area stay outside the scrollable
region. When space runs out, filing context and the central workspace can scroll
together. This is deliberate: enlarged text must remain readable, and opening setup
must not squeeze results to zero height. Tab brings offscreen controls into view.
The scrollbar and wheel over workspace backgrounds provide pointer access; tables,
text, and comboboxes keep their native wheel behavior. At narrow enlarged sizes,
metadata uses two columns, and secondary action groups wrap.

## New controls

- **View → Text size:** 100%, 125%, 150%, 175%, or 200%. Existing named font objects
  update in place; controls and results are not recreated. Draft values, disclosures,
  selected rows, and inner scroll positions are retained. Decorative spacing does not
  double along with text. Preferences are session-only.
- **View → Use Windows system colors:** uses Windows semantic colors for workspace
  surfaces, text, selections, and focus, with a native primary-button layout. This
  lets the workspace use the user's configured contrast palette. It does not change
  Windows settings, automatically enable high contrast, or persist outside the app.
  The option is disabled on non-Windows platforms.
- **Help → Keyboard shortcuts (F1):** discoverable commands in a native dialog.
- **Help → Current status and summary (F8):** a user-triggered native text dialog
  containing outcome/status, any disabled reason, and the result summary or recovery
  guidance. Status is not communicated by color alone.

| Key | Action |
| --- | --- |
| Tab / Shift+Tab | Traverse controls; read-only text does not trap Tab |
| Ctrl+O / Ctrl+Shift+O | Browse filing / output folder |
| Ctrl+Enter | Invoke the current primary action, only when enabled |
| Alt+S / Alt+D / Alt+G | Toggle setup / details / diagnostics |
| F6 | Focus the active result table, diagnostic text, or recovery text |
| Ctrl+Tab / Ctrl+Shift+Tab | Switch result tabs from their contents |
| Arrow keys, then Tab | Select a table row, then reach its full detail text |
| Ctrl+A / Ctrl+C | Select all / copy read-only text |
| Ctrl+Plus / Ctrl+Minus / Ctrl+0 | Increase / decrease / reset text size |

Source and output browse controls now have distinct Filing… and Folder… labels.
Native menus expose their full names. Result paths, pages, tabs, and detail text all
use the shared font layer. Selection remains read-only; shortcuts do not introduce
automatic extraction or file launches.

## Validation

Final validation: **246 tests passed on two consecutive full-suite runs**. Full-
repository Ruff, dependency checks, diff whitespace checks, CLI help, and wheel/sdist
build passed. Isolated imports from the built wheel verified the new UI modules are
packaged and do not load the heavy extraction stack. No dependencies were added.

Automated coverage includes:

- A 15-case live-layout matrix: all five text sizes at 640×700, 720×820, and
  1120×820, with long filing/client labels and expanded setup.
- A complete Tab cycle at 200%, including offscreen controls and automatic scrolling.
- Native forward/backward traversal, protected read-only text, result-tab navigation,
  help/status commands, and disabled-primary shortcut behavior.
- Long warning results and recovery text, plus running/error/success controls at
  200% and the minimum window size.
- Font-object identity, retained draft/disclosures, selected rows and scroll position,
  and Windows system-color/style mappings.
- Existing real HTML extraction/workbook verification and bounded PDF regressions.

Layout updates are coalesced after Tk geometry changes; top-level windows own idle
callbacks so shutdown can cancel them cleanly. UI test fixtures also fail on Tk
callback exceptions instead of accepting a passing assertion with a broken event loop.

## Manual review gate — still open

Automated geometry/focus checks are not visual or assistive-technology approval.
No screenshot review, Narrator/NVDA session, or actual Windows high-contrast scheme
switch has been verified in this environment. Tk's native-looking controls do not
by themselves prove screen-reader naming, announcements, or UI Automation support.
The explicit labels and F8 text dialog are aids, not a claim of screen-reader parity
or accessibility certification.

Before final rollout:

1. Run the live workspace using only the keyboard; browse a synthetic filing,
   inspect settings, extract, review long checks, and exercise Retry.
2. Repeat at 100%, 150%, and 200%, with setup open/closed and narrow/wide windows.
   Confirm readable focus indicators and no missing or truncated actions.
3. With an existing Windows contrast theme, enable the system-colors option and
   review normal, disabled, selected, warning, and error states.
4. With Narrator or NVDA, check field names/values, menu navigation, table headings,
   full detail text, F8 summary, and error recovery. Record any missing announcements.
5. Review screenshots with realistic long paths, statement titles, and warning text.

Phase 8 remains the final realistic-data/visual review and rollout phase. OS-level
contrast switching, assistive-technology installation, persistent session storage,
and a UI framework migration are not part of this change.
