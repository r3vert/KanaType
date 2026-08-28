# KanaType boot.py — deliberately tiny (a boot.py bug can lock you out of the drive).
#
# M0: the host always owns CIRCUITPY; every app runs read-only.
# M3 (matrix installed): detect hold-WAKE-at-power-on here and remount the
#     filesystem writable + disable USB MSC for note/editor sessions.
# M4: read the nvm flag for deep-sleep wake routing into quick-note.
#
# Nothing to do yet — presence of this file reserves the slot.
