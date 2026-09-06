pragma Singleton
import QtQuick 2.15

// Source unique de vérité pour tout le style de l'interface.
// Modifier les couleurs ici change toute l'application.
QtObject {
    // Fond
    readonly property color backgroundTop: "#060a12"
    readonly property color backgroundBottom: "#0c1526"

    // Panneaux / bordures
    readonly property color panelBackground: "#0f1b2e"
    readonly property color panelBorder: "#1c2f4a"

    // Texte
    readonly property color textPrimary: "#e6f1ff"
    readonly property color textSecondary: "#5d7ba3"

    // Couleurs associées aux états de l'assistant
    readonly property color colorIdle: "#33c7ff"
    readonly property color colorListening: "#33ffb0"
    readonly property color colorThinking: "#b073ff"
    readonly property color colorSpeaking: "#ff9d47"

    readonly property string fontFamily: "Segoe UI"

    // Durées d'animation standardisées
    readonly property int animFast: 180
    readonly property int animMedium: 500
    readonly property int animSlow: 1400

    // Renvoie la couleur associée à un état donné
    function stateColor(state) {
        switch (state) {
            case "listening": return colorListening
            case "thinking": return colorThinking
            case "speaking": return colorSpeaking
            default: return colorIdle
        }
    }

    // Renvoie le libellé affiché pour un état donné
    function stateLabel(state) {
        switch (state) {
            case "listening": return "À L'ÉCOUTE"
            case "thinking": return "ANALYSE EN COURS"
            case "speaking": return "RÉPONSE EN COURS"
            default: return "EN VEILLE"
        }
    }
}
