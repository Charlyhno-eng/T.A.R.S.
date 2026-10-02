import QtQuick 2.15
import theme 1.0

Rectangle {
    gradient: Gradient {
        GradientStop {
            position: 0.0
            color: Qt.rgba(Theme.backgroundTop.r, Theme.backgroundTop.g,
                           Theme.backgroundTop.b, 0.78)
        }
        GradientStop {
            position: 1.0
            color: Qt.rgba(Theme.backgroundBottom.r, Theme.backgroundBottom.g,
                           Theme.backgroundBottom.b, 0.82)
        }
    }

    // Static haze and fine grain suggest frosted glass without capturing the desktop.
    Canvas {
        anchors.fill: parent

        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()

        function haze(ctx, x, y, radius, strength) {
            var tint = Theme.textSecondary
            var glow = ctx.createRadialGradient(x, y, 0, x, y, radius)
            glow.addColorStop(0, Qt.rgba(tint.r, tint.g, tint.b, strength))
            glow.addColorStop(0.45, Qt.rgba(tint.r, tint.g, tint.b, strength * 0.4))
            glow.addColorStop(1, Qt.rgba(tint.r, tint.g, tint.b, 0))
            ctx.fillStyle = glow
            ctx.fillRect(0, 0, width, height)
        }

        onPaint: {
            if (width <= 0 || height <= 0)
                return

            var ctx = getContext("2d")
            ctx.reset()

            var spread = Math.max(width, height)
            haze(ctx, width * 0.18, height * 0.12, spread * 0.65, 0.09)
            haze(ctx, width * 0.85, height * 0.78, spread * 0.55, 0.07)

            // A fixed seed keeps repeated paints from flickering.
            var seed = 137
            for (var y = 0; y < height; y += 3) {
                for (var x = 0; x < width; x += 3) {
                    seed = (seed * 1664525 + 1013904223) >>> 0
                    var value = seed / 4294967296
                    ctx.fillStyle = value > 0.5
                        ? Qt.rgba(1, 1, 1, (value - 0.5) * 0.045)
                        : Qt.rgba(0, 0, 0, (0.5 - value) * 0.045)
                    ctx.fillRect(x, y, 1, 1)
                }
            }
        }
    }
}
