pragma Singleton
import QtQuick 2.15

QtObject {
    readonly property color backgroundTop: "#060a12"
    readonly property color backgroundBottom: "#0c1526"

    readonly property color panelBackground: "#0f1b2e"
    readonly property color panelBorder: "#1c2f4a"

    readonly property color textPrimary: "#e6f1ff"
    readonly property color textSecondary: "#5d7ba3"

    readonly property color colorIdle: "#33c7ff"
    readonly property color colorListening: "#33ffb0"
    readonly property color colorThinking: "#b073ff"
    readonly property color colorSpeaking: "#ff9d47"

    readonly property string fontFamily: "Segoe UI"

    readonly property int animFast: 180
    readonly property int animMedium: 500
    readonly property int animSlow: 1400

    function stateColor(state) {
        switch (state) {
            case "listening": return colorListening
            case "thinking": return colorThinking
            case "speaking": return colorSpeaking
            default: return colorIdle
        }
    }

    function stateLabel(state, language) {
        var english = language === "en"
        switch (state) {
            case "listening": return english ? "LISTENING" : "À L'ÉCOUTE"
            case "thinking": return english ? "PROCESSING" : "ANALYSE EN COURS"
            case "speaking": return english ? "SPEAKING" : "RÉPONSE EN COURS"
            default: return english ? "STANDBY" : "EN VEILLE"
        }
    }
}
