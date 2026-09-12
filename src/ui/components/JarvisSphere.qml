import QtQuick 2.15
import theme 1.0

Item {
    id: root

    property string sphereState: "idle"
    property bool animationsEnabled: true
    property color activeColor: Theme.stateColor(sphereState)

    signal pressed()
    signal released()

    implicitWidth: 340
    implicitHeight: 340
    scale: 1.0

    Behavior on activeColor {
        ColorAnimation {
            duration: Theme.animMedium
        }
    }

    Behavior on scale {
        NumberAnimation {
            id: hoverAnim
            duration: Theme.animFast
            easing.type: Easing.OutQuad
        }
    }

    Repeater {
        model: 4

        delegate: Rectangle {
            anchors.centerIn: parent

            width: root.width * (0.62 + index * 0.13)
            height: width
            radius: width / 2

            color: "transparent"

            border.width: 1
            border.color: Qt.rgba(
                root.activeColor.r,
                root.activeColor.g,
                root.activeColor.b,
                0.10 - index * 0.02
            )
        }
    }

    Canvas {
        id: outerRing

        anchors.centerIn: parent
        width: root.width * 0.92
        height: width

        NumberAnimation on rotation {
            from: 0
            to: 360
            duration: 9000
            loops: Animation.Infinite
            running: root.animationsEnabled
        }

        onPaint: {
            var ctx = getContext("2d")

            ctx.reset()
            ctx.save()

            ctx.translate(width / 2, height / 2)

            ctx.strokeStyle = root.activeColor
            ctx.globalAlpha = 0.55
            ctx.lineWidth = 2

            var segments = 26
            var radius = width / 2 - 4

            for (var i = 0; i < segments; i++) {
                if (i % 3 === 0)
                    continue

                var a0 = (i / segments) * Math.PI * 2
                var a1 = a0 + (Math.PI * 2 / segments) * 0.6

                ctx.beginPath()
                ctx.arc(0, 0, radius, a0, a1)
                ctx.stroke()
            }

            ctx.restore()
        }

        Connections {
            target: root

            function onActiveColorChanged() {
                outerRing.requestPaint()
            }
        }
    }

    Canvas {
        id: innerRing

        anchors.centerIn: parent
        width: root.width * 0.74
        height: width

        NumberAnimation on rotation {
            from: 360
            to: 0
            duration: 6000
            loops: Animation.Infinite
            running: root.animationsEnabled
        }

        onPaint: {
            var ctx = getContext("2d")

            ctx.reset()
            ctx.save()

            ctx.translate(width / 2, height / 2)

            ctx.strokeStyle = root.activeColor
            ctx.globalAlpha = 0.35
            ctx.lineWidth = 1.5

            var segments = 18
            var radius = width / 2 - 3

            for (var i = 0; i < segments; i++) {
                if (i % 4 === 0)
                    continue

                var a0 = (i / segments) * Math.PI * 2
                var a1 = a0 + (Math.PI * 2 / segments) * 0.5

                ctx.beginPath()
                ctx.arc(0, 0, radius, a0, a1)
                ctx.stroke()
            }

            ctx.restore()
        }

        Connections {
            target: root

            function onActiveColorChanged() {
                innerRing.requestPaint()
            }
        }
    }

    Canvas {
        id: core

        anchors.centerIn: parent
        width: root.width * 0.52
        height: width

        SequentialAnimation on scale {
            loops: Animation.Infinite
            running: root.animationsEnabled

            NumberAnimation {
                from: 0.98
                to: 1.02
                duration: Theme.animSlow
                easing.type: Easing.InOutSine
            }

            NumberAnimation {
                from: 1.02
                to: 0.98
                duration: Theme.animSlow
                easing.type: Easing.InOutSine
            }
        }

        onPaint: {
            var ctx = getContext("2d")

            ctx.reset()

            var w = width
            var h = height
            var cx = w / 2
            var cy = h / 2
            var r = w / 2

            var grad = ctx.createRadialGradient(
                cx - r * 0.3,
                cy - r * 0.35,
                r * 0.05,
                cx,
                cy,
                r
            )

            grad.addColorStop(
                0.0,
                Qt.rgba(1, 1, 1, 0.9)
            )

            grad.addColorStop(
                0.28,
                Qt.rgba(
                    root.activeColor.r,
                    root.activeColor.g,
                    root.activeColor.b,
                    0.95
                )
            )

            grad.addColorStop(
                0.75,
                Qt.rgba(
                    root.activeColor.r,
                    root.activeColor.g,
                    root.activeColor.b,
                    0.55
                )
            )

            grad.addColorStop(
                1.0,
                Qt.rgba(
                    root.activeColor.r,
                    root.activeColor.g,
                    root.activeColor.b,
                    0.05
                )
            )

            ctx.beginPath()
            ctx.fillStyle = grad
            ctx.arc(cx, cy, r, 0, Math.PI * 2)
            ctx.fill()

            ctx.strokeStyle = Qt.rgba(1, 1, 1, 0.15)
            ctx.lineWidth = 1

            var offsets = [-0.45, -0.15, 0.15, 0.45]

            for (var i = 0; i < offsets.length; i++) {
                var oy = offsets[i] * r

                var ellW = r * 1.8 * Math.sqrt(
                    Math.max(
                        0,
                        1 - offsets[i] * offsets[i] * 2.2
                    )
                )

                ctx.beginPath()

                ctx.ellipse(
                    cx - ellW / 2,
                    cy + oy - r * 0.06,
                    ellW,
                    r * 0.12
                )

                ctx.stroke()
            }
        }

        Connections {
            target: root

            function onActiveColorChanged() {
                core.requestPaint()
            }
        }

        Component.onCompleted: requestPaint()
    }

    MouseArea {
        anchors.centerIn: parent

        width: core.width * 1.15
        height: width

        cursorShape: Qt.PointingHandCursor
        hoverEnabled: true

        onPressed: root.pressed()
        onReleased: root.released()

        onEntered: {
            root.scale = 1.05
        }

        onExited: {
            root.scale = 1.0
        }
    }
}
