import QtQuick 2.15
import theme 1.0

// Anneau de petites particules en orbite lente autour de la sphère.
// Purement décoratif, ne porte aucune logique métier.
Item {
    id: root

    property color particleColor: Theme.colorIdle
    property int count: 40
    property real radius: 170

    implicitWidth: radius * 2 + 20
    implicitHeight: implicitWidth

    Behavior on particleColor { ColorAnimation { duration: Theme.animMedium } }

    Item {
        id: spinner
        anchors.centerIn: parent
        width: 1
        height: 1

        NumberAnimation on rotation {
            from: 0; to: 360
            duration: 42000
            loops: Animation.Infinite
        }

        Repeater {
            model: root.count
            delegate: Rectangle {
                property real angle: (index / root.count) * Math.PI * 2
                readonly property bool major: index % 5 === 0

                x: root.radius * Math.cos(angle)
                y: root.radius * Math.sin(angle)
                width: major ? 3 : 1.5
                height: width
                radius: width / 2
                color: root.particleColor
                opacity: major ? 0.5 : 0.18
            }
        }
    }
}
