#!/usr/bin/env python3
"""Enable an automatic warm low-blue-light tint while the reader is active."""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("Usage: add-night-reading-mode.py <MangaReaderApp.swift>")

path = Path(sys.argv[1])
source = path.read_text()

if "isNightReadingModeActive" in source and "NIGHT_READING_MODE_OVERLAY" in source:
    print("Automatic night-reading mode is already installed; skipping.")
    raise SystemExit(0)

state_anchor = """    @State private var swipeProgressDismissTask: Task<Void, Never>?
"""
state_replacement = state_anchor + """    @State private var isNightReadingModeActive = false
"""
if state_anchor not in source:
    raise SystemExit("Could not find ReaderView swipe state insertion point")
source = source.replace(state_anchor, state_replacement, 1)

overlay_anchor = """            .coordinateSpace(name: "reader")
            .statusBarHidden(true)
"""
overlay_replacement = """            // NIGHT_READING_MODE_OVERLAY: warm tint is scoped to the reader only.
            .overlay {
                if isNightReadingModeActive {
                    Color(red: 1.0, green: 0.72, blue: 0.42)
                        .opacity(0.32)
                        .blendMode(.multiply)
                        .ignoresSafeArea()
                        .allowsHitTesting(false)
                        .accessibilityHidden(true)
                }
            }
            .coordinateSpace(name: "reader")
            .statusBarHidden(true)
"""
if overlay_anchor not in source:
    raise SystemExit("Could not find ReaderView full-screen overlay insertion point")
source = source.replace(overlay_anchor, overlay_replacement, 1)

task_anchor = """        .task { await prepareArchive() }
"""
task_replacement = """        .onAppear {
            isNightReadingModeActive = true
        }
        .task { await prepareArchive() }
"""
if task_anchor not in source:
    raise SystemExit("Could not find ReaderView task modifier")
source = source.replace(task_anchor, task_replacement, 1)

scene_anchor = """        .onChange(of: scenePhase) { phase in
            if phase != .active { stopAutoPage() }
        }
"""
scene_replacement = """        .onChange(of: scenePhase) { phase in
            if phase == .active {
                isNightReadingModeActive = true
            } else {
                isNightReadingModeActive = false
                stopAutoPage()
            }
        }
"""
if scene_anchor not in source:
    raise SystemExit("Could not find ReaderView scenePhase handler")
source = source.replace(scene_anchor, scene_replacement, 1)

disappear_anchor = """        .onDisappear {
            stopAutoPage()
            swipeProgressDismissTask?.cancel()
        }
"""
disappear_replacement = """        .onDisappear {
            isNightReadingModeActive = false
            stopAutoPage()
            swipeProgressDismissTask?.cancel()
        }
"""
if disappear_anchor not in source:
    raise SystemExit("Could not find ReaderView onDisappear handler")
source = source.replace(disappear_anchor, disappear_replacement, 1)

close_anchor = """    private func closeReader() {
        stopAutoPage()
        dismiss()
    }
"""
close_replacement = """    private func closeReader() {
        isNightReadingModeActive = false
        stopAutoPage()
        dismiss()
    }
"""
if close_anchor not in source:
    raise SystemExit("Could not find ReaderView closeReader function")
source = source.replace(close_anchor, close_replacement, 1)

path.write_text(source)
print(f"Added automatic warm low-blue-light reading tint to {path}")
