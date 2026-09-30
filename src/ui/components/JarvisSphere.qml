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

            shape(ctx, base, energy, 0)
            var fill = ctx.createRadialGradient(cx - base * 0.34, cy - base * 0.42,
                                                base * 0.03, cx + base * 0.12,
                                                cy + base * 0.16, base * 1.38)
            fill.addColorStop(0, Qt.rgba(0.82 + color.r * 0.18,
                                         0.82 + color.g * 0.18,
                                         0.82 + color.b * 0.18, 1))
            fill.addColorStop(0.28, Qt.rgba(color.r * 0.8 + 0.15,
                                            color.g * 0.8 + 0.15,
                                            color.b * 0.8 + 0.15, 1))
            fill.addColorStop(0.68, Qt.rgba(color.r * 0.48, color.g * 0.5,
                                            color.b * 0.58, 1))
            fill.addColorStop(1, Qt.rgba(color.r * 0.09, color.g * 0.12,
                                         color.b * 0.18, 1))
            ctx.fillStyle = fill
            ctx.fill()

            // Keep the light and shadow inside the animated silhouette.
            ctx.save()
            shape(ctx, base, energy, 0)
            ctx.clip()
            var shade = ctx.createLinearGradient(cx, cy - base, cx, cy + base)
            shade.addColorStop(0, Qt.rgba(1, 1, 1, 0.12))
            shade.addColorStop(0.55, Qt.rgba(0, 0, 0, 0))
            shade.addColorStop(1, Qt.rgba(0, 0, 0, 0.35))
            ctx.fillStyle = shade
            ctx.fillRect(cx - base * 1.3, cy - base * 1.3,
                         base * 2.6, base * 2.6)

            var shine = ctx.createRadialGradient(cx - base * 0.4, cy - base * 0.57,
                                                 0, cx - base * 0.4, cy - base * 0.57,
                                                 base * 0.55)
            shine.addColorStop(0, Qt.rgba(1, 1, 1, 0.42))
            shine.addColorStop(1, Qt.rgba(1, 1, 1, 0))
            ctx.fillStyle = shine
            ctx.fillRect(cx - base, cy - base, base * 2, base * 2)
            ctx.restore()
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
