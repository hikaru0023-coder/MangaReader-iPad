#!/usr/bin/env python3
"""Add one-finger horizontal page scrubbing and a temporary bottom progress bar."""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("Usage: add-horizontal-page-scrub.py <MangaReaderApp.swift>")

path = Path(sys.argv[1])
source = path.read_text()

if "onSwipeChanged:" in source and "ReaderSwipePhase" in source:
    print("Horizontal page scrubbing is already installed; skipping.")
    raise SystemExit(0)

state_anchor = """    @State private var zoomScale: CGFloat = 1
    @State private var imageOffset: CGSize = .zero
"""
state_replacement = state_anchor + """
    @State private var showsSwipeProgress = false
    @State private var isSwipeDragging = false
    @State private var swipeStartPage = 0
    @State private var swipeTargetPage = 0
    @State private var swipeDirectionForward = true
    @State private var swipeProgressDismissTask: Task<Void, Never>?
"""
if state_anchor not in source:
    raise SystemExit("Could not locate ReaderView zoom state insertion point")
source = source.replace(state_anchor, state_replacement, 1)

onpan_anchor = """                                onPan: { translation in
                                    guard zoomScale > 1.01 else { return }
                                    imageOffset = CGSize(width: imageOffset.width + translation.width,
                                                         height: imageOffset.height + translation.height)
                                    clampImageOffset(viewSize: geometry.size)
                                }
"""
onpan_replacement = """                                onPan: { translation in
                                    guard zoomScale > 1.01 else { return }
                                    imageOffset = CGSize(width: imageOffset.width + translation.width,
                                                         height: imageOffset.height + translation.height)
                                    clampImageOffset(viewSize: geometry.size)
                                },
                                onSwipeChanged: { translation, phase in
                                    handleHorizontalPageSwipe(translation, phase: phase)
                                }
"""
if onpan_anchor not in source:
    raise SystemExit("Could not locate ReaderImageGestureOverlay onPan callback")
source = source.replace(onpan_anchor, onpan_replacement, 1)

auto_button_anchor = """                Button {
                    toggleAutoPage()
                } label: {
"""
progress_overlay = """                if showsSwipeProgress && !readingPages.isEmpty {
                    VStack {
                        Spacer()
                        VStack(spacing: 8) {
                            HStack(spacing: 12) {
                                Text("第 \\\\(swipeTargetPage + 1) / \\\\(readingPages.count) 頁")
                                    .font(.system(size: 13, weight: .bold, design: .rounded))
                                    .monospacedDigit()
                                Spacer()
                                Text(swipeDirectionForward ? "向右：快轉" : "向左：回頁")
                                    .font(.system(size: 11, weight: .medium))
                                    .foregroundStyle(.white.opacity(0.72))
                            }
                            GeometryReader { bar in
                                ZStack(alignment: .leading) {
                                    Capsule().fill(.white.opacity(0.20))
                                    Capsule()
                                        .fill(Color(red: 0.63, green: 0.49, blue: 1.0))
                                        .frame(width: bar.size.width * CGFloat(swipeTargetPage + 1) / CGFloat(max(readingPages.count, 1)))
                                }
                            }
                            .frame(height: 6)
                        }
                        .foregroundStyle(.white)
                        .padding(.horizontal, 16)
                        .padding(.vertical, 12)
                        .background(.black.opacity(0.72), in: RoundedRectangle(cornerRadius: 15))
                        .overlay(RoundedRectangle(cornerRadius: 15).stroke(.white.opacity(0.16), lineWidth: 1))
                        .padding(.horizontal, 28)
                        .padding(.bottom, 30)
                    }
                    .transition(.move(edge: .bottom).combined(with: .opacity))
                    .allowsHitTesting(false)
                }

"""
if auto_button_anchor not in source:
    raise SystemExit("Could not locate auto-page button insertion point")
source = source.replace(auto_button_anchor, progress_overlay + auto_button_anchor, 1)

source = source.replace("""        .onDisappear { stopAutoPage() }
""", """        .onDisappear {
            stopAutoPage()
            swipeProgressDismissTask?.cancel()
        }
""", 1)

handle_tap_anchor = """    private func handleTap(at x: CGFloat, width: CGFloat) {
        guard !readingPages.isEmpty, !isLoading else { return }
        if x < width / 3 {
            changePage(by: -1)
        } else if x >= width * 2 / 3 {
            changePage(by: 1)
        } else {
            closeReader()
        }
    }
"""
handle_swipe = handle_tap_anchor + """
    private func handleHorizontalPageSwipe(_ translation: CGSize, phase: ReaderSwipePhase) {
        switch phase {
        case .began:
            swipeProgressDismissTask?.cancel()
            swipeStartPage = currentPage
            swipeTargetPage = currentPage
            isSwipeDragging = false

        case .changed, .ended:
            guard !readingPages.isEmpty, !isLoading else { return }
            let horizontal = translation.width
            let vertical = translation.height
            guard abs(horizontal) >= 24, abs(horizontal) > abs(vertical) * 1.2 else {
                return
            }

            if !isSwipeDragging {
                isSwipeDragging = true
                withAnimation(.easeOut(duration: 0.15)) {
                    showsSwipeProgress = true
                }
            }

            swipeDirectionForward = horizontal >= 0
            let pageDelta = Int((horizontal / 55).rounded(.towardZero))
            swipeTargetPage = min(readingPages.count - 1, max(0, swipeStartPage + pageDelta))

            if phase == .ended {
                isSwipeDragging = false
                if swipeTargetPage != currentPage {
                    currentPage = swipeTargetPage
                }
                swipeProgressDismissTask?.cancel()
                swipeProgressDismissTask = Task { @MainActor in
                    try? await Task.sleep(nanoseconds: 1_200_000_000)
                    guard !Task.isCancelled else { return }
                    withAnimation(.easeOut(duration: 0.22)) {
                        showsSwipeProgress = false
                    }
                }
            }

        case .cancelled:
            isSwipeDragging = false
            withAnimation(.easeOut(duration: 0.18)) {
                showsSwipeProgress = false
            }
        }
    }
"""
if handle_tap_anchor not in source:
    raise SystemExit("Could not find handleTap function")
source = source.replace(handle_tap_anchor, handle_swipe, 1)

start_marker = """/// One gesture surface owns all reader-image touches. Pinch and two-finger pan
/// are allowed to recognize together, so the pan recognizer cannot block pinch-in.
private struct ReaderImageGestureOverlay: UIViewRepresentable {
"""
start = source.find(start_marker)
if start < 0:
    raise SystemExit("Could not find ReaderImageGestureOverlay declaration")

new_gesture = """/// Directional swipe progress for the manga page scrub gesture.
private enum ReaderSwipePhase {
    case began
    case changed
    case ended
    case cancelled
}

/// One gesture surface owns all reader-image touches. One finger scrubs pages;
/// two fingers pinch or pan. Tap waits for the one-finger pan to fail so swipes
/// do not accidentally trigger the old left/right tap-to-turn behavior.
private struct ReaderImageGestureOverlay: UIViewRepresentable {
    let onTap: (CGFloat) -> Void
    let onZoom: (CGFloat) -> Void
    let onPan: (CGSize) -> Void
    let onSwipeChanged: (CGSize, ReaderSwipePhase) -> Void

    func makeCoordinator() -> Coordinator {
        Coordinator(onTap: onTap, onZoom: onZoom, onPan: onPan, onSwipeChanged: onSwipeChanged)
    }

    func makeUIView(context: Context) -> UIView {
        let view = UIView(frame: .zero)
        view.backgroundColor = .clear
        view.isOpaque = false
        view.isMultipleTouchEnabled = true

        let tap = UITapGestureRecognizer(target: context.coordinator,
                                         action: #selector(Coordinator.handleTap(_:)))
        tap.numberOfTapsRequired = 1
        tap.numberOfTouchesRequired = 1
        tap.cancelsTouchesInView = false
        tap.delaysTouchesBegan = false
        tap.delaysTouchesEnded = false
        tap.delegate = context.coordinator
        view.addGestureRecognizer(tap)

        let pinch = UIPinchGestureRecognizer(target: context.coordinator,
                                             action: #selector(Coordinator.handlePinch(_:)))
        pinch.cancelsTouchesInView = false
        pinch.delaysTouchesBegan = false
        pinch.delaysTouchesEnded = false
        pinch.delegate = context.coordinator
        view.addGestureRecognizer(pinch)

        let twoFingerPan = UIPanGestureRecognizer(target: context.coordinator,
                                                  action: #selector(Coordinator.handlePan(_:)))
        twoFingerPan.minimumNumberOfTouches = 2
        twoFingerPan.maximumNumberOfTouches = 2
        twoFingerPan.cancelsTouchesInView = false
        twoFingerPan.delaysTouchesBegan = false
        twoFingerPan.delaysTouchesEnded = false
        twoFingerPan.delegate = context.coordinator
        view.addGestureRecognizer(twoFingerPan)

        let oneFingerSwipe = UIPanGestureRecognizer(target: context.coordinator,
                                                    action: #selector(Coordinator.handleSwipe(_:)))
        oneFingerSwipe.minimumNumberOfTouches = 1
        oneFingerSwipe.maximumNumberOfTouches = 1
        oneFingerSwipe.cancelsTouchesInView = false
        oneFingerSwipe.delaysTouchesBegan = false
        oneFingerSwipe.delaysTouchesEnded = false
        oneFingerSwipe.delegate = context.coordinator
        view.addGestureRecognizer(oneFingerSwipe)
        tap.require(toFail: oneFingerSwipe)

        context.coordinator.containerView = view
        return view
    }

    func updateUIView(_ uiView: UIView, context: Context) {
        context.coordinator.onTap = onTap
        context.coordinator.onZoom = onZoom
        context.coordinator.onPan = onPan
        context.coordinator.onSwipeChanged = onSwipeChanged
    }

    final class Coordinator: NSObject, UIGestureRecognizerDelegate {
        var onTap: (CGFloat) -> Void
        var onZoom: (CGFloat) -> Void
        var onPan: (CGSize) -> Void
        var onSwipeChanged: (CGSize, ReaderSwipePhase) -> Void
        weak var containerView: UIView?

        init(onTap: @escaping (CGFloat) -> Void,
             onZoom: @escaping (CGFloat) -> Void,
             onPan: @escaping (CGSize) -> Void,
             onSwipeChanged: @escaping (CGSize, ReaderSwipePhase) -> Void) {
            self.onTap = onTap
            self.onZoom = onZoom
            self.onPan = onPan
            self.onSwipeChanged = onSwipeChanged
        }

        func gestureRecognizer(_ gestureRecognizer: UIGestureRecognizer,
                               shouldRecognizeSimultaneouslyWith otherGestureRecognizer: UIGestureRecognizer) -> Bool {
            true
        }

        @objc func handleTap(_ recognizer: UITapGestureRecognizer) {
            guard recognizer.state == .ended, let view = containerView else { return }
            onTap(recognizer.location(in: view).x)
        }

        @objc func handlePinch(_ recognizer: UIPinchGestureRecognizer) {
            switch recognizer.state {
            case .began:
                recognizer.scale = 1
            case .changed:
                let factor = recognizer.scale
                recognizer.scale = 1
                if factor.isFinite && factor > 0 {
                    onZoom(factor)
                }
            default:
                break
            }
        }

        @objc func handlePan(_ recognizer: UIPanGestureRecognizer) {
            guard recognizer.state == .changed, let view = containerView else { return }
            let delta = recognizer.translation(in: view)
            recognizer.setTranslation(.zero, in: view)
            onPan(CGSize(width: delta.x, height: delta.y))
        }

        @objc func handleSwipe(_ recognizer: UIPanGestureRecognizer) {
            guard let view = containerView else { return }
            let translation = recognizer.translation(in: view)
            let size = CGSize(width: translation.x, height: translation.y)
            switch recognizer.state {
            case .began:
                onSwipeChanged(.zero, .began)
            case .changed:
                onSwipeChanged(size, .changed)
            case .ended:
                onSwipeChanged(size, .ended)
            case .cancelled, .failed:
                onSwipeChanged(size, .cancelled)
            default:
                break
            }
        }
    }
}
"""
source = source[:start] + new_gesture
path.write_text(source)
print(f"Added horizontal page scrubbing to {path}")
