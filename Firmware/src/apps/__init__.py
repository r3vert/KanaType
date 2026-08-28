"""KanaType apps. Each module exposes run(ctx); the launcher imports one
app lazily per boot and calls supervisor.reload() when it returns."""
import time


def stub(ctx, name, detail):
    """Shared placeholder screen for apps that haven't landed yet.
    Screen budget is ~16 ASCII chars per line (k8x12 is 8 px wide)."""
    from kanatype import ui

    # 4 lines max with the 16px menu font (SCREEN_PITCH x 4 fills the panel).
    ctx.display.root_group = ui.screen(
        [name, "Not built yet", detail, "Any key: menu"]
    )
    while True:
        if ctx.input.poll():
            return
        time.sleep(0.02)
