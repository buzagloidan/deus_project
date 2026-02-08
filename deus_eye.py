#!/usr/bin/env python3
"""
DEUS Eye - Animated desktop companion with video frames
Based on "The Machine" from Person of Interest
"""

import sys
import os
import glob

try:
    import objc
    from AppKit import (
        NSApplication,
        NSWindow,
        NSWindowStyleMaskBorderless,
        NSBackingStoreBuffered,
        NSFloatingWindowLevel,
        NSImage,
        NSScreen,
        NSTimer,
        NSApplicationActivationPolicyAccessory,
        NSAffineTransform,
        NSGraphicsContext,
        NSCompositingOperationSourceOver,
        NSView,
        NSColor,
    )
    import Quartz
    from Foundation import NSMakeRect, NSObject
except ImportError:
    print("Installing required packages...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyobjc-framework-Cocoa", "pyobjc-framework-Quartz"])
    print("Please run the script again.")
    sys.exit(0)

# Configuration
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FRAMES_DIR = os.path.join(SCRIPT_DIR, "deus_frames_transparent")
EYE_SIZE = 700  # Size of the eye window
FOLLOW_SPEED = 0.025  # How quickly the eye follows (lazy)
EDGE_PADDING = 50
FRAME_RATE = 30  # Playback speed (frames per second)


class AnimatedImageView(NSView):
    """Custom view for displaying animated frames"""

    def initWithFrame_(self, frame):
        self = objc.super(AnimatedImageView, self).initWithFrame_(frame)
        if self is None:
            return None
        self.current_image = None
        return self

    def setImage_(self, image):
        self.current_image = image
        self.setNeedsDisplay_(True)

    def drawRect_(self, rect):
        if self.current_image is None:
            return

        bounds = self.bounds()
        self.current_image.drawInRect_fromRect_operation_fraction_(
            bounds,
            NSMakeRect(0, 0, 0, 0),
            NSCompositingOperationSourceOver,
            1.0
        )


class DeusEyeApp(NSObject):
    def init(self):
        self = objc.super(DeusEyeApp, self).init()
        if self is None:
            return None

        self.current_x = 100.0
        self.current_y = 100.0
        self.target_x = 100.0
        self.target_y = 100.0

        # Animation state
        self.frames = []
        self.current_frame = 0
        self.frame_counter = 0.0

        # Mouse tracking for direction
        self.last_mouse_x = 0.0
        self.last_mouse_y = 0.0
        self.velocity_x = 0.0
        self.velocity_y = 0.0

        return self

    def loadFrames(self):
        """Load all transparent frames"""
        frame_paths = sorted(glob.glob(os.path.join(FRAMES_DIR, "frame_*.png")))

        if not frame_paths:
            print(f"Error: No frames found in {FRAMES_DIR}")
            sys.exit(1)

        print(f"Loading {len(frame_paths)} frames...")

        for i, path in enumerate(frame_paths):
            image = NSImage.alloc().initWithContentsOfFile_(path)
            if image:
                self.frames.append(image)
            if (i + 1) % 500 == 0:
                print(f"Loaded {i + 1}/{len(frame_paths)} frames...")

        print(f"Loaded {len(self.frames)} frames successfully!")

    def createWindow(self):
        # Load frames first
        self.loadFrames()

        # Get screen dimensions
        screen = NSScreen.mainScreen()
        screen_frame = screen.frame()

        # Create window
        rect = NSMakeRect(100, 100, EYE_SIZE, EYE_SIZE)
        self.window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            rect,
            NSWindowStyleMaskBorderless,
            NSBackingStoreBuffered,
            False
        )

        # Configure window
        self.window.setLevel_(NSFloatingWindowLevel)
        self.window.setOpaque_(False)
        self.window.setBackgroundColor_(NSColor.clearColor())
        self.window.setIgnoresMouseEvents_(True)
        self.window.setHasShadow_(False)
        self.window.setCollectionBehavior_(1 << 0 | 1 << 3)

        # Create animated image view
        self.image_view = AnimatedImageView.alloc().initWithFrame_(NSMakeRect(0, 0, EYE_SIZE, EYE_SIZE))
        self.image_view.setImage_(self.frames[0])

        self.window.contentView().addSubview_(self.image_view)
        self.window.makeKeyAndOrderFront_(None)

        # Store screen bounds
        self.screen_width = screen_frame.size.width
        self.screen_height = screen_frame.size.height

        # Initialize position at center
        self.current_x = self.screen_width / 2
        self.current_y = self.screen_height / 2

        # Start animation timer (60 FPS for smooth movement)
        self.timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            1.0 / 60.0,
            self,
            "updateAnimation:",
            None,
            True
        )

    def updateAnimation_(self, timer):
        # Keep eye centered on screen
        center_x = (self.screen_width - EYE_SIZE) / 2.0
        center_y = (self.screen_height - EYE_SIZE) / 2.0

        if self.current_x != center_x or self.current_y != center_y:
            self.current_x = center_x
            self.current_y = center_y
            self.window.setFrameOrigin_((self.current_x, self.current_y))

        # Update animation frame
        self.frame_counter += FRAME_RATE / 60.0
        if self.frame_counter >= 1.0:
            self.frame_counter = 0.0
            self.current_frame = (self.current_frame + 1) % len(self.frames)
            self.image_view.setImage_(self.frames[self.current_frame])


def main():
    print("Starting DEUS Eye (Video Animation)...")
    print("Press Ctrl+C in terminal to quit.\n")

    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

    delegate = DeusEyeApp.alloc().init()
    delegate.createWindow()

    print("\nDEUS Eye is now running!")
    app.run()


if __name__ == "__main__":
    main()
