import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import theme 1.0

Column {
    id: root
    spacing: 10
    property bool english: assistant.language === "en"

    function reload() {
        var saved = desktop.windowStartup
        fullscreen.checked = saved.fullscreen
        widthField.text = saved.width.toString()
        heightField.text = saved.height.toString()
        xField.text = saved.x.toString()
        yField.text = saved.y.toString()
        feedback.text = ""
    }

    Text {
        text: root.english ? "WINDOW AT STARTUP" : "FENÊTRE AU LANCEMENT"
        color: Theme.colorIdle
        font.family: Theme.fontFamily
        font.pixelSize: 11
        font.bold: true
        font.letterSpacing: 2
    }
    CheckBox {
        id: fullscreen
        text: root.english ? "Full screen" : "Plein écran"
        contentItem: Text {
            text: fullscreen.text
            leftPadding: fullscreen.indicator.width + fullscreen.spacing
            color: Theme.textPrimary
            verticalAlignment: Text.AlignVCenter
        }
    }
    GridLayout {
        width: parent.width
        columns: 2
        enabled: !fullscreen.checked
        opacity: enabled ? 1 : 0.5
        Text { text: root.english ? "Width (px)" : "Largeur (px)"; color: Theme.textSecondary }
        TextField {
            id: widthField
            Layout.fillWidth: true
            validator: IntValidator { bottom: 600; top: 100000 }
            selectByMouse: true
        }
        Text { text: root.english ? "Height (px)" : "Hauteur (px)"; color: Theme.textSecondary }
        TextField {
            id: heightField
            Layout.fillWidth: true
            validator: IntValidator { bottom: 560; top: 100000 }
            selectByMouse: true
        }
        Text { text: "X (px)"; color: Theme.textSecondary }
        TextField {
            id: xField
            Layout.fillWidth: true
            validator: IntValidator { bottom: -100000; top: 100000 }
            selectByMouse: true
        }
        Text { text: "Y (px)"; color: Theme.textSecondary }
        TextField {
            id: yField
            Layout.fillWidth: true
            validator: IntValidator { bottom: -100000; top: 100000 }
            selectByMouse: true
        }
    }
    Text {
        width: parent.width
        text: root.english
            ? "X/Y position the window from the desktop's top-left corner. Minimum size: 600 × 560. Changes apply on the next launch."
            : "X/Y placent la fenêtre depuis le coin supérieur gauche du bureau. Taille minimale : 600 × 560. Les changements s'appliquent au prochain lancement."
        wrapMode: Text.WordWrap
        color: Theme.textSecondary
        font.pixelSize: 12
    }
    SettingsButton {
        text: root.english ? "Save window settings" : "Enregistrer la fenêtre"
        enabled: widthField.acceptableInput && heightField.acceptableInput
            && xField.acceptableInput && yField.acceptableInput
        onClicked: {
            var saved = desktop.saveWindowStartup(fullscreen.checked,
                Number(widthField.text), Number(heightField.text), Number(xField.text), Number(yField.text))
            feedback.text = saved
                ? (root.english ? "Saved for the next launch." : "Enregistré pour le prochain lancement.")
                : (root.english ? "Could not save window settings." : "Impossible d'enregistrer la fenêtre.")
        }
    }
    Text {
        id: feedback
        width: parent.width
        wrapMode: Text.WordWrap
        color: Theme.textSecondary
        font.pixelSize: 12
    }
}
