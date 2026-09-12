import QtQuick 2.15
import theme 1.0

Column {
    id: root

    property string sphereState: "idle"
    property string language: "fr"
    property color accent: Theme.stateColor(sphereState)

    spacing: 14

    Behavior on accent {
        ColorAnimation {
            duration: Theme.animMedium
        }
    }

    Text {
        anchors.horizontalCenter: parent.horizontalCenter

        text: Theme.stateLabel(root.sphereState, root.language)

        color: root.accent

        font.family: Theme.fontFamily
        font.pixelSize: 15
        font.bold: true
        font.letterSpacing: 4
    }
}
