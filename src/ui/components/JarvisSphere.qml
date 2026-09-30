import QtQuick 2.15
import theme 1.0

Item {
    id: root

    property string sphereState: "idle"
    property bool animationsEnabled: true
    property color activeColor: Theme.stateColor(sphereState)
    property real phase: 0
    property bool holding: false

    signal pressed()
    signal released()

    implicitWidth: 340
    implicitHeight: 340

    Behavior on activeColor { ColorAnimation { duration: Theme.animMedium } }

    Timer {
        interval: 33
        repeat: true
        running: root.animationsEnabled
        onTriggered: {
            root.phase += root.sphereState === "listening" ? 0.095 :
                          root.sphereState === "speaking" ? 0.075 : 0.045
            blob.requestPaint()
        }
    }

    Canvas {
        id: blob
        anchors.fill: parent
        antialiasing: true

        function shape(ctx, radius, wobble, offset) {
            var points = 96
            ctx.beginPath()
            for (var i = 0; i <= points; ++i) {
                var angle = i * Math.PI * 2 / points
                var wave = Math.sin(angle * 3 + root.phase + offset) * 0.065 +
                           Math.sin(angle * 5 - root.phase * 0.73 + offset) * 0.035 +
                           Math.sin(angle * 7 + root.phase * 0.51) * 0.017
                var r = radius * (1 + wave * wobble)
                var x = width / 2 + Math.cos(angle) * r
                var y = height / 2 + Math.sin(angle) * r
                if (i === 0) ctx.moveTo(x, y)
                else ctx.lineTo(x, y)
            }
            ctx.closePath()
        }

        onPaint: {
            var ctx = getContext("2d")
            ctx.reset()
            var cx = width / 2
            var cy = height / 2
            var energy = root.sphereState === "listening" ? 1.65 :
                         root.sphereState === "speaking" ? 1.35 :
                         root.sphereState === "thinking" ? 1.15 : 0.8
            var base = Math.min(width, height) * (root.holding ? 0.36 : 0.34)
            var color = root.activeColor

            // Soft outer layers make the moving contour readable against the dark canvas.
            for (var layer = 3; layer >= 1; --layer) {
                shape(ctx, base + layer * 13, energy, layer * 0.4)
                ctx.fillStyle = Qt.rgba(color.r, color.g, color.b, 0.025 + (4 - layer) * 0.012)
                ctx.fill()
            }

            shape(ctx, base, energy, 0)
            var fill = ctx.createRadialGradient(cx - base * 0.35, cy - base * 0.5,
                                                base * 0.08, cx, cy, base * 1.3)
            fill.addColorStop(0, Qt.rgba(0.9, 1, 1, 0.95))
            fill.addColorStop(0.25, Qt.rgba(color.r, color.g, color.b, 0.95))
            fill.addColorStop(0.72, Qt.rgba(color.r * 0.45, color.g * 0.55, color.b * 0.65, 0.95))
            fill.addColorStop(1, Qt.rgba(color.r * 0.12, color.g * 0.18, color.b * 0.25, 0.95))
            ctx.fillStyle = fill
            ctx.fill()
            ctx.strokeStyle = Qt.rgba(color.r, color.g, color.b, 0.7)
            ctx.lineWidth = 2
            ctx.stroke()

            shape(ctx, base * 0.78, energy * 0.55, 0.8)
            ctx.strokeStyle = Qt.rgba(1, 1, 1, 0.17)
            ctx.lineWidth = 1
            ctx.stroke()

            var shine = ctx.createRadialGradient(cx - base * 0.36, cy - base * 0.55,
                                                 0, cx - base * 0.36, cy - base * 0.55,
                                                 base * 0.65)
            shine.addColorStop(0, Qt.rgba(1, 1, 1, 0.22))
            shine.addColorStop(1, Qt.rgba(1, 1, 1, 0))
            shape(ctx, base * 0.93, energy, 0)
            ctx.fillStyle = shine
            ctx.fill()
        }

        Connections {
            target: root
            function onActiveColorChanged() { blob.requestPaint() }
            function onHoldingChanged() { blob.requestPaint() }
        }
        Component.onCompleted: requestPaint()
    }

    Text {
        anchors.centerIn: parent
        text: root.sphereState === "listening" ? "●" : "T"
        color: "#f5fcff"
        opacity: 0.85
        font.family: Theme.fontFamily
        font.pixelSize: root.sphereState === "listening" ? 24 : 44
        font.bold: true
        font.letterSpacing: 2
    }

    MouseArea {
        anchors.centerIn: parent
        width: parent.width * 0.76
        height: width
        cursorShape: Qt.PointingHandCursor
        hoverEnabled: true
        onPressed: {
            root.holding = true
            root.pressed()
        }
        onReleased: {
            root.holding = false
            root.released()
        }
        onCanceled: {
            if (root.holding) {
                root.holding = false
                root.released()
            }
        }
    }
}
