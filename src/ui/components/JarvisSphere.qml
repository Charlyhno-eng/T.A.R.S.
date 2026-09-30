import QtQuick 2.15
import theme 1.0

Item {
    id: root

    property string sphereState: "idle"
    property bool animationsEnabled: true
    property bool interactionEnabled: true
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
            robot.requestPaint()
        }
    }

    Canvas {
        id: robot
        anchors.fill: parent
        antialiasing: true

        function panel(ctx, points, fill, stroke, lineWidth) {
            ctx.beginPath()
            ctx.moveTo(points[0], points[1])
            for (var i = 2; i < points.length; i += 2)
                ctx.lineTo(points[i], points[i + 1])
            ctx.closePath()
            ctx.fillStyle = fill
            ctx.fill()
            if (stroke) {
                ctx.strokeStyle = stroke
                ctx.lineWidth = lineWidth || 1
                ctx.stroke()
            }
        }

        function roundedPanel(ctx, x, y, w, h, radius, fill, stroke) {
            ctx.beginPath()
            ctx.moveTo(x + radius, y)
            ctx.lineTo(x + w - radius, y)
            ctx.quadraticCurveTo(x + w, y, x + w, y + radius)
            ctx.lineTo(x + w, y + h - radius)
            ctx.quadraticCurveTo(x + w, y + h, x + w - radius, y + h)
            ctx.lineTo(x + radius, y + h)
            ctx.quadraticCurveTo(x, y + h, x, y + h - radius)
            ctx.lineTo(x, y + radius)
            ctx.quadraticCurveTo(x, y, x + radius, y)
            ctx.closePath()
            ctx.fillStyle = fill
            ctx.fill()
            if (stroke) {
                ctx.strokeStyle = stroke
                ctx.lineWidth = 1.3
                ctx.stroke()
            }
        }

        function eye(ctx, x, y, width, lift) {
            ctx.beginPath()
            ctx.moveTo(x - width / 2, y + 5)
            ctx.quadraticCurveTo(x, y - lift, x + width / 2, y + 5)
            ctx.stroke()
        }

        onPaint: {
            var ctx = getContext("2d")
            ctx.reset()
            var scale = Math.min(width, height) / 340
            var energy = root.sphereState === "listening" ? 1.6 :
                         root.sphereState === "speaking" ? 1.35 :
                         root.sphereState === "thinking" ? 1.15 : 0.75
            var pulse = Math.sin(root.phase) * energy
            var bend = Math.sin(root.phase * 0.69) * energy * 6
            var breathe = Math.sin(root.phase * 0.56) * energy * 3
            var accent = root.activeColor
            var cyan = Qt.rgba(0.26, 0.78, 1, 1)

            ctx.save()
            ctx.translate(width / 2, height / 2)
            ctx.scale(scale * (root.holding ? 1.055 : 1), scale * (root.holding ? 1.055 : 1))
            ctx.translate(0, -4 + breathe)
            ctx.transform(1, 0, bend / 230, 1, 0, 0)

            // Diffuse light follows the head without changing the mascot's blue face.
            var aura = ctx.createRadialGradient(0, 0, 35, 0, 0, 160)
            aura.addColorStop(0, Qt.rgba(accent.r, accent.g, accent.b, 0.24))
            aura.addColorStop(0.7, Qt.rgba(accent.r, accent.g, accent.b, 0.08))
            aura.addColorStop(1, Qt.rgba(accent.r, accent.g, accent.b, 0))
            ctx.fillStyle = aura
            ctx.fillRect(-165, -165, 330, 330)

            var shadow = ctx.createRadialGradient(0, 111, 4, 0, 111, 119)
            shadow.addColorStop(0, Qt.rgba(0, 0, 0, 0.58))
            shadow.addColorStop(1, Qt.rgba(0, 0, 0, 0))
            ctx.fillStyle = shadow
            ctx.fillRect(-125, 78, 250, 70)

            // The dark side and bright top give the flexible shell its depth.
            var side = ctx.createLinearGradient(68, 0, 106, 0)
            side.addColorStop(0, "#343b43")
            side.addColorStop(0.4, "#10151c")
            side.addColorStop(1, "#050a11")
            panel(ctx, [72 + bend, -111, 100 + bend * 0.6, -98,
                        104 - bend * 0.3, 96, 73 - bend, 118], side, "#68717a", 1.2)
            var top = ctx.createLinearGradient(0, -126, 0, -96)
            top.addColorStop(0, "#f2f5f5")
            top.addColorStop(0.55, "#9da6ac")
            top.addColorStop(1, "#444d55")
            panel(ctx, [-71 - bend, -109, -49, -125 - pulse,
                        79 + bend, -114, 100 + bend * 0.6, -98,
                        72 + bend, -107], top, "#bbc2c7", 1)

            var shell = ctx.createLinearGradient(-76, -12, 80, 30)
            shell.addColorStop(0, "#d6dce0")
            shell.addColorStop(0.18, "#69737c")
            shell.addColorStop(0.36, "#252d35")
            shell.addColorStop(0.77, "#111820")
            shell.addColorStop(1, "#59636c")
            roundedPanel(ctx, -78 - bend, -111 - pulse, 155 + bend * 2,
                         229 + pulse * 1.5, 20, shell, "#77818a")

            // Silver side rails are the strongest visual link to the app mascot.
            var leftRail = ctx.createLinearGradient(-78, 0, -49, 0)
            leftRail.addColorStop(0, "#e5e9e9")
            leftRail.addColorStop(0.35, "#b4bdc3")
            leftRail.addColorStop(1, "#505b65")
            panel(ctx, [-69 - bend, -103 - pulse, -49 - bend * 0.65, -105,
                        -54 + bend * 0.4, 112 + pulse * 0.5,
                        -77 - bend, 101], leftRail, "#282f37", 1.2)
            var rightRail = ctx.createLinearGradient(52, 0, 83, 0)
            rightRail.addColorStop(0, "#4b5661")
            rightRail.addColorStop(0.48, "#f0f1ef")
            rightRail.addColorStop(1, "#87929b")
            panel(ctx, [52 + bend * 0.65, -106, 73 + bend, -105 - pulse,
                        78 - bend, 103, 57 - bend * 0.45, 115],
                  rightRail, "#363e47", 1.2)

            var glass = ctx.createLinearGradient(-47, -73, 61, 36)
            glass.addColorStop(0, "#22313b")
            glass.addColorStop(0.26, "#050b12")
            glass.addColorStop(0.73, "#080f18")
            glass.addColorStop(1, "#1f2b36")
            roundedPanel(ctx, -49, -81 - pulse * 0.45, 103, 100 + pulse * 0.3,
                         8, glass, "#070b10")
            panel(ctx, [-46, -77, -7, -78, -34, 15, -47, 15],
                  Qt.rgba(0.65, 0.83, 0.95, 0.055))

            // Rounded blue eyes and smile stay readable as the head flexes.
            var faceY = -39 + Math.sin(root.phase * 1.12) * energy * 1.8
            ctx.lineCap = "round"
            ctx.lineJoin = "round"
            ctx.strokeStyle = Qt.rgba(cyan.r, cyan.g, cyan.b, 0.22)
            ctx.lineWidth = 9
            ctx.save()
            ctx.translate(pulse * 1.8, 0)
            ctx.scale(1 + pulse * 0.014, 1 - pulse * 0.012)
            eye(ctx, -23, faceY, 21, 18 + pulse)
            eye(ctx, 27, faceY + 2, 21, 18 - pulse)
            ctx.beginPath()
            ctx.moveTo(-12, faceY + 33)
            ctx.quadraticCurveTo(3, faceY + 47 + pulse * 0.8,
                                 17, faceY + 32)
            ctx.stroke()
            ctx.strokeStyle = "#a9edff"
            ctx.lineWidth = 3.5
            eye(ctx, -23, faceY, 21, 18 + pulse)
            eye(ctx, 27, faceY + 2, 21, 18 - pulse)
            ctx.beginPath()
            ctx.moveTo(-12, faceY + 33)
            ctx.quadraticCurveTo(3, faceY + 47 + pulse * 0.8,
                                 17, faceY + 32)
            ctx.stroke()
            ctx.restore()

            // Segmented lower face and small luminous status slit.
            var lower = ctx.createLinearGradient(0, 19, 0, 113)
            lower.addColorStop(0, "#3b444d")
            lower.addColorStop(0.42, "#171e26")
            lower.addColorStop(1, "#080e16")
            panel(ctx, [-50, 21, 55, 20, 57 - bend * 0.45, 112,
                        -54 + bend * 0.4, 111], lower, "#080d13", 1.5)
            ctx.strokeStyle = "#59636c"
            ctx.lineWidth = 1.2
            ctx.beginPath()
            ctx.moveTo(-52, 40); ctx.lineTo(55, 40)
            ctx.moveTo(-53, 58); ctx.lineTo(56, 58)
            ctx.moveTo(-54, 88); ctx.lineTo(57, 88)
            ctx.stroke()
            var slit = ctx.createLinearGradient(-26, 0, 27, 0)
            slit.addColorStop(0, Qt.rgba(0.1, 0.5, 0.9, 0))
            slit.addColorStop(0.25, "#4ecaff")
            slit.addColorStop(0.75, "#b6f0ff")
            slit.addColorStop(1, Qt.rgba(0.1, 0.5, 0.9, 0))
            roundedPanel(ctx, -28, 67 + pulse * 0.35, 56, 3, 1.5, slit)

            // Joint lines emphasize that the metal panels move as one head.
            ctx.strokeStyle = Qt.rgba(0.06, 0.09, 0.12, 0.8)
            ctx.lineWidth = 1.4
            ctx.beginPath()
            ctx.moveTo(-70 - bend * 0.8, -38)
            ctx.lineTo(-54, -33)
            ctx.moveTo(54, -35)
            ctx.lineTo(73 + bend * 0.8, -39)
            ctx.stroke()
            ctx.restore()
        }

        Connections {
            target: root
            function onActiveColorChanged() { robot.requestPaint() }
            function onHoldingChanged() { robot.requestPaint() }
        }
        Component.onCompleted: requestPaint()
    }

    MouseArea {
        anchors.centerIn: parent
        enabled: root.interactionEnabled
        width: parent.width * 0.76
        height: width
        cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
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
