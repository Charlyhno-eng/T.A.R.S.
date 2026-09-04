import QtQuick 2.15
import theme 1.0

// Bandeau supérieur : logo/mascotte, titre et petit indicateur "en ligne".
Row {
    id: root
    spacing: 14
    height: 46

    Image {
        source: "../../public/tars-mascot.png"
        width: 40
        height: 40
        fillMode: Image.PreserveAspectFit
        anchors.verticalCenter: parent.verticalCenter
        visible: status === Image.Ready
    }

    Column {
        anchors.verticalCenter: parent.verticalCenter
        spacing: 2

        Text {
            text: "T.A.R.S."
            color: Theme.textPrimary
            font.family: Theme.fontFamily
            font.pixelSize: 20
            font.bold: true
            font.letterSpacing: 3
        }

        Row {
            spacing: 6

            Rectangle {
                width: 7
                height: 7
                radius: 3.5
                color: Theme.colorListening
                anchors.verticalCenter: parent.verticalCenter
            }

            Text {
                text: "SYSTÈME EN LIGNE"
                color: Theme.textSecondary
                font.family: Theme.fontFamily
                font.pixelSize: 11
                font.letterSpacing: 2
            }
        }
    }
}
