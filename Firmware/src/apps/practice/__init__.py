"""Kana practice — DJT-style drill (see PLAN.md M1).

Flow: config screen (categories, mode, font) -> drill loop.
Exit combo returns to config from the drill; exiting config returns to menu.
"""


def run(ctx):
    from apps.practice import config, drill

    while True:
        opts = config.run_config(ctx)
        if opts is None:
            return  # back to launcher menu
        drill.run(ctx, opts)  # EXIT in the drill falls back to config
