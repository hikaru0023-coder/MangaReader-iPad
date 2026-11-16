#!/usr/bin/env python3
"""Patch the reader image gestures so pinch-in and two-finger pan work together."""
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("Usage: fix-reader-zoom.py <MangaReaderApp.swift>")

source = Path(sys.argv[1])
text = source.read_text()

old_image = '''                        .clipped()
                        .contentShape(Rectangle())
                        .gesture(imageManipulationGesture(viewSize: geometry.size))
                        .overlay {
                            if zoomScale > 1.01 {
                                TwoFingerPanOverlay { translation in
                                    imageOffset = CGSize(width: imageOffset.width + translation.width,
                                                         height: imageOffset.height + translation.height)
                                    clampImageOffset(viewSize: geometry.size)
                                }
                            }
                        }
                        .simultaneousGesture(SpatialTapGesture().onEnded { value in
                            handleTap(at: value.location.x, width: geometry.size.width)
                        })'''
new_image = '''                        .clipped()
                        .overlay {
                            ReaderImageGestureOverlay(
                                onTap: { x in
                                    handleTap(at: x, width: geometry.size.width)
                                },
                                onZoom: { scaleFactor in
                                    // Apply each pinch delta incrementally. This supports both
                                    // pinch-out (zoom in) and pinch-in (zoom back down).
                                    zoomScale = min(5, max(1, zoomScale * scaleFactor))
                                    if zoomScale <= 1.01 {
                                        zoomScale = 1
                                        imageOffset = .zero
                                    }
                                    clampImageOffset(viewSize: geometry.size)
                                },
                                onPan: { translation in
                                    guard zoomScale > 1.01 else { return }
                                    imageOffset = CGSize(width: imageOffset.width + translation.width,
                                                         height: imageOffset.height + translation.height)
                                    clampImageOffset(viewSize: geometry.size)
                                }
                            )
                        }'''
if old_image not in text:
    raise SystemExit("Could not find the expected ReaderView image gesture chain")
text = text.replace(old_image, new_image, 1)

old_func = '''    private func imageManipulationGesture(viewSize: CGSize) -> some Gesture {
        MagnificationGesture()
            .onChanged { value in
                zoomScale = min(5, max(1, zoomAnchor * value))
                clampImageOffset(viewSize: viewSize)
            }
            .onEnded { _ in
                zoomAnchor = zoomScale
                if zoomScale <= 1.01 {
                    zoomScale = 1
                    zoomAnchor = 1
                    imageOffset = .zero
                }
            }
    }

'''
if old_func not in text:
    raise SystemExit("Could not find imageManipulationGesture function")
text = text.replace(old_func, "", 1)
text = text.replace("    @State private var zoomAnchor: CGFloat = 1\n", "", 1)
text = text.replace("        zoomAnchor = 1\n", "", 1)

old_overlay = '''/// A dedicated two-or-more-finger pan recognizer. It stays transparent and only
/// participates after the image has been magnified, matching the Android gesture model.
private struct TwoFingerPanOverlay: UIViewRepresentable {
    let onPan: (CGSize) -> Void

    func makeCoordinator() -> Coordinator { Coordinator(onPan: onPan) }

    func makeUIView(context: Context) -> UIView {
        let view = UIView(frame: .zero)
        view.backgroundColor = .clear
        view.isMultipleTouchEnabled = true

        let pan = UIPanGestureRecognizer(target: context.coordinator,
                                         action: #selector(Coordinator.handlePan(_:)))
        pan.minimumNumberOfTouches = 2
        pan.cancelsTouchesInView = false
        pan.delaysTouchesBegan = false
        pan.delaysTouchesEnded = false
        view.addGestureRecognizer(pan)
        context.coordinator.containerView = view
        return view
    }

    func updateUIView(_ uiView: UIView, context: Context) {
        context.coordinator.onPan = onPan
    }

    final class Coordinator: NSObject {
        var onPan: (CGSize) -> Void
        weak var containerView: UIView?

        init(onPan: @escaping (CGSize) -> Void) {
            self.onPan = onPan
        }

        @objc func handlePan(_ recognizer: UIPanGestureRecognizer) {
            guard recognizer.state == .changed, let view = containerView else { return }
            let delta = recognizer.translation(in: view)
            recognizer.setTranslation(.zero, in: view)
            onPan(CGSize(width: delta.x, height: delta.y))
        }
    }
}
'''
new_overlay = '''/// One gesture surface owns all reader-image touches. Pinch and two-finger pan
/// are allowed to recognize together, so the pan recognizer cannot block pinch-in.
private struct ReaderImageGestureOverlay: UIViewRepresentable {
    let onTap: (CGFloat) -> Void
    let onZoom: (CGFloat) -> Void
    let onPan: (CGSize) -> Void

    func makeCoordinator() -> Coordinator {
        Coordinator(onTap: onTap, onZoom: onZoom, onPan: onPan)
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

        let pan = UIPanGestureRecognizer(target: context.coordinator,
                                         action: #selector(Coordinator.handlePan(_:)))
        pan.minimumNumberOfTouches = 2
        pan.maximumNumberOfTouches = 2
        pan.cancelsTouchesInView = false
        pan.delaysTouchesBegan = false
        pan.delaysTouchesEnded = false
        pan.delegate = context.coordinator
        view.addGestureRecognizer(pan)

        context.coordinator.containerView = view
        return view
    }

    func updateUIView(_ uiView: UIView, context: Context) {
        context.coordinator.onTap = onTap
        context.coordinator.onZoom = onZoom
        context.coordinator.onPan = onPan
    }

    final class Coordinator: NSObject, UIGestureRecognizerDelegate {
        var onTap: (CGFloat) -> Void
        var onZoom: (CGFloat) -> Void
        var onPan: (CGSize) -> Void
        weak var containerView: UIView?

        init(onTap: @escaping (CGFloat) -> Void,
             onZoom: @escaping (CGFloat) -> Void,
             onPan: @escaping (CGSize) -> Void) {
            self.onTap = onTap
            self.onZoom = onZoom
            self.onPan = onPan
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
    }
}
'''
if old_overlay not in text:
    raise SystemExit("Could not find original TwoFingerPanOverlay implementation")
text = text.replace(old_overlay, new_overlay, 1)

if "zoomAnchor" in text or "MagnificationGesture()" in text or "TwoFingerPanOverlay" in text:
    raise SystemExit("Old zoom implementation references remain after patch")

source.write_text(text)
print(f"Updated pinch-in/pinch-out and two-finger pan handling in {source}")
