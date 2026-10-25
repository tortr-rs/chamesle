// the chamesle sign-in screen: a lock screen with the clock first, any key or click slides it up to sign in,
// like windows does it. sddm hands us userModel, sessionModel, sddm (login, power) and config (theme.conf)
import QtQuick
import QtQuick.Controls

Rectangle {
    id: root
    width: 1920
    height: 1080
    color: "#0b1a33"

    readonly property string fontName: config.font || "Inter"
    // everything is drawn for 1080p and scaled to the screen
    readonly property real s: Math.min(width / 1920, height / 1080)
    // preview=signin in theme.conf starts on the sign-in box, for screenshots of it
    property bool locked: config.preview !== "signin"
    property int userIndex: userModel.lastIndex >= 0 ? userModel.lastIndex : 0
    property int sessionIndex: sessionModel.lastIndex >= 0 ? sessionModel.lastIndex : 0
    property string error: ""

    // the users, read through a repeater: sddm's model only gives its roles to delegates
    Repeater {
        id: users
        model: userModel
        delegate: Item {
            property string login: model.name
            property string realName: model.realName
            property string icon: model.icon
            property bool needsPassword: model.needsPassword
        }
    }
    readonly property var user: users.count > 0 ? users.itemAt(Math.min(userIndex, users.count - 1)) : null
    readonly property string userName: user ? user.login : ""
    readonly property string shownName: user ? (user.realName || user.login) : ""

    function unlock() {
        if (!locked) return
        locked = false
        password.forceActiveFocus()
    }
    function signIn() {
        if (busy.running) return
        error = ""
        busy.running = true
        sddm.login(userName, password.text, sessionIndex)
    }

    Connections {
        target: sddm
        function onLoginFailed() {
            busy.running = false
            password.text = ""
            error = "That password isn't right. Try again."
            shake.restart()
            password.forceActiveFocus()
        }
        function onLoginSucceeded() { busy.running = false }
    }

    // both backgrounds stay loaded: the blurred one fades in under the sign-in box
    Image {
        anchors.fill: parent
        source: config.background || "assets/background.jpg"
        fillMode: Image.PreserveAspectCrop
        asynchronous: false
    }
    Image {
        anchors.fill: parent
        source: config.backgroundBlur || "assets/background-blur.jpg"
        fillMode: Image.PreserveAspectCrop
        opacity: root.locked ? 0 : 1
        Behavior on opacity { NumberAnimation { duration: 350; easing.type: Easing.OutCubic } }
    }

    // ---- the lock screen ----
    Item {
        id: lock
        width: parent.width
        height: parent.height
        y: root.locked ? 0 : -parent.height * 0.12
        opacity: root.locked ? 1 : 0
        visible: opacity > 0
        Behavior on y { NumberAnimation { duration: 350; easing.type: Easing.OutCubic } }
        Behavior on opacity { NumberAnimation { duration: 250 } }

        Text {
            id: time
            anchors.horizontalCenter: parent.horizontalCenter
            y: parent.height * 0.11
            color: "white"
            font.family: root.fontName
            font.pixelSize: 132 * root.s
            font.weight: Font.DemiBold
            text: Qt.formatTime(clock.now, config.clock === "12" ? "h:mm" : "HH:mm")
            style: Text.Raised
            styleColor: "#30000000"
        }
        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: time.bottom
            anchors.topMargin: 2 * root.s
            color: "white"
            font.family: root.fontName
            font.pixelSize: 26 * root.s
            font.weight: Font.Medium
            text: Qt.formatDate(clock.now, "dddd, d MMMM")
        }
    }
    Timer {
        id: clock
        property date now: new Date()
        interval: 1000
        running: true
        repeat: true
        onTriggered: now = new Date()
    }

    // ---- signing in ----
    Item {
        id: signin
        anchors.fill: parent
        opacity: root.locked ? 0 : 1
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: 300 } }

        Column {
            id: box
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.verticalCenter: parent.verticalCenter
            anchors.verticalCenterOffset: -40 * root.s
            spacing: 18 * root.s

            // the picture people set, or the plain one
            Item {
                anchors.horizontalCenter: parent.horizontalCenter
                width: 176 * root.s
                height: width
                Image {
                    id: face
                    anchors.fill: parent
                    source: root.user && root.user.icon ? root.user.icon : "assets/user.svg"
                    sourceSize: Qt.size(width * 2, height * 2)
                    fillMode: Image.PreserveAspectCrop
                    visible: false
                    onStatusChanged: if (status === Image.Error) source = "assets/user.svg"
                }
                // round crop without shaders: works on machines with no 3d acceleration too
                Canvas {
                    id: round
                    anchors.fill: parent
                    property var img: face.source
                    onImgChanged: { loadImage(img); requestPaint() }
                    onImageLoaded: requestPaint()
                    onPaint: {
                        var c = getContext("2d")
                        c.reset()
                        c.beginPath()
                        c.arc(width / 2, height / 2, width / 2, 0, 2 * Math.PI)
                        c.closePath()
                        c.clip()
                        if (isImageLoaded(img)) c.drawImage(img, 0, 0, width, height)
                        else { c.fillStyle = "#e6e9ee"; c.fill() }
                    }
                }
            }

            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                color: "white"
                font.family: root.fontName
                font.pixelSize: 30 * root.s
                font.weight: Font.DemiBold
                text: root.shownName
            }

            // the password box, with the arrow inside it like windows
            Item {
                id: field
                anchors.horizontalCenter: parent.horizontalCenter
                width: 320 * root.s
                height: 40 * root.s
                visible: !root.user || root.user.needsPassword
                SequentialAnimation {
                    id: shake
                    NumberAnimation { target: field; property: "anchors.horizontalCenterOffset"; to: -12; duration: 50 }
                    NumberAnimation { target: field; property: "anchors.horizontalCenterOffset"; to: 12; duration: 70 }
                    NumberAnimation { target: field; property: "anchors.horizontalCenterOffset"; to: -6; duration: 60 }
                    NumberAnimation { target: field; property: "anchors.horizontalCenterOffset"; to: 0; duration: 50 }
                }
                Rectangle {
                    anchors.fill: parent
                    radius: 6 * root.s
                    color: password.activeFocus ? "#a0101828" : "#80101828"
                    border.color: "#40ffffff"
                    border.width: 1
                    Rectangle {  // the accent line under the box when it's active
                        anchors.bottom: parent.bottom
                        anchors.horizontalCenter: parent.horizontalCenter
                        width: parent.width - 2 * parent.radius
                        height: 2
                        color: "#4f9dff"
                        visible: password.activeFocus
                    }
                }
                TextInput {
                    id: password
                    anchors.left: parent.left
                    anchors.right: reveal.left
                    anchors.leftMargin: 14 * root.s
                    anchors.verticalCenter: parent.verticalCenter
                    color: "white"
                    font.family: root.fontName
                    font.pixelSize: 17 * root.s
                    echoMode: reveal.pressed ? TextInput.Normal : TextInput.Password
                    passwordCharacter: "•"
                    clip: true
                    selectByMouse: true
                    selectionColor: "#4f9dff"
                    onAccepted: root.signIn()
                    onTextChanged: if (text.length) root.error = ""
                    Keys.onEscapePressed: { text = ""; root.locked = true }
                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: "Password"
                        color: "#c8ffffff"
                        font: password.font
                        visible: !password.text && !password.preeditText
                    }
                }
                MouseArea {
                    id: reveal
                    anchors.right: go.left
                    anchors.verticalCenter: parent.verticalCenter
                    width: 32 * root.s
                    height: parent.height
                    visible: password.text.length > 0
                    cursorShape: Qt.PointingHandCursor
                    Image {
                        anchors.centerIn: parent
                        source: "assets/eye.svg"
                        width: 18 * root.s
                        height: width
                        sourceSize: Qt.size(width * 2, height * 2)
                        opacity: reveal.pressed ? 1 : 0.7
                    }
                }
                MouseArea {
                    id: go
                    anchors.right: parent.right
                    anchors.rightMargin: 4 * root.s
                    anchors.verticalCenter: parent.verticalCenter
                    width: 32 * root.s
                    height: 32 * root.s
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.signIn()
                    Rectangle {
                        anchors.fill: parent
                        radius: 5 * root.s
                        color: go.pressed ? "#3a7fe0" : (go.containsMouse ? "#4f9dff" : "#30ffffff")
                    }
                    hoverEnabled: true
                    Image {
                        anchors.centerIn: parent
                        source: "assets/arrow.svg"
                        width: 18 * root.s
                        height: width
                        sourceSize: Qt.size(width * 2, height * 2)
                        visible: !busy.running
                    }
                    BusyIndicator {
                        id: busy
                        anchors.centerIn: parent
                        width: 22 * root.s
                        height: width
                        running: false
                        visible: running
                    }
                }
            }

            // no password on this account (autologin users): just a button
            Rectangle {
                anchors.horizontalCenter: parent.horizontalCenter
                visible: root.user && !root.user.needsPassword
                width: 160 * root.s
                height: 40 * root.s
                radius: 6 * root.s
                color: plain.pressed ? "#3a7fe0" : "#4f9dff"
                Text {
                    anchors.centerIn: parent
                    text: "Sign in"
                    color: "white"
                    font.family: root.fontName
                    font.pixelSize: 17 * root.s
                    font.weight: Font.Medium
                }
                MouseArea { id: plain; anchors.fill: parent; onClicked: root.signIn() }
            }

            Text {
                anchors.horizontalCenter: parent.horizontalCenter
                color: "white"
                font.family: root.fontName
                font.pixelSize: 15 * root.s
                text: root.error || (keyboard.capsLock ? "Caps Lock is on" : " ")
                opacity: text.trim() ? 1 : 0
            }
        }

        // other people on this computer, bottom left
        Column {
            anchors.left: parent.left
            anchors.bottom: parent.bottom
            anchors.margins: 28 * root.s
            spacing: 4 * root.s
            visible: users.count > 1
            Repeater {
                model: userModel
                delegate: Rectangle {
                    width: 260 * root.s
                    height: 52 * root.s
                    radius: 6 * root.s
                    color: index === root.userIndex ? "#38ffffff" : (pick.containsMouse ? "#20ffffff" : "transparent")
                    Row {
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.left: parent.left
                        anchors.leftMargin: 10 * root.s
                        spacing: 12 * root.s
                        Canvas {
                            width: 34 * root.s
                            height: width
                            property string img: model.icon || "assets/user.svg"
                            Component.onCompleted: loadImage(img)
                            onImageLoaded: requestPaint()
                            onPaint: {
                                var c = getContext("2d")
                                c.reset(); c.beginPath()
                                c.arc(width / 2, height / 2, width / 2, 0, 2 * Math.PI)
                                c.closePath(); c.clip()
                                if (isImageLoaded(img)) c.drawImage(img, 0, 0, width, height)
                                else { c.fillStyle = "#e6e9ee"; c.fill() }
                            }
                        }
                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: model.realName || model.name
                            color: "white"
                            font.family: root.fontName
                            font.pixelSize: 16 * root.s
                        }
                    }
                    MouseArea {
                        id: pick
                        anchors.fill: parent
                        hoverEnabled: true
                        onClicked: { root.userIndex = index; password.text = ""; root.error = ""; password.forceActiveFocus() }
                    }
                }
            }
        }
    }

    // bottom right on both screens: which desktop, and power
    Row {
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 24 * root.s
        spacing: 6 * root.s

        Repeater {
            id: sessions
            model: sessionModel
            delegate: Item { property string label: model.name }
        }
        Corner {
            visible: sessions.count > 1
            icon: "assets/desktop.svg"
            label: sessions.count ? sessions.itemAt(Math.min(root.sessionIndex, sessions.count - 1)).label : ""
            onClicked: sessionMenu.open()
            Menu {
                id: sessionMenu
                y: -height - 8
                Repeater {
                    model: sessionModel
                    MenuItem {
                        text: model.name
                        checkable: true
                        checked: index === root.sessionIndex
                        onTriggered: root.sessionIndex = index
                    }
                }
            }
        }
        Corner {
            icon: "assets/power.svg"
            onClicked: powerMenu.open()
            Menu {
                id: powerMenu
                y: -height - 8
                MenuItem { text: "Sleep"; enabled: sddm.canSuspend; onTriggered: sddm.suspend() }
                MenuItem { text: "Shut down"; enabled: sddm.canPowerOff; onTriggered: sddm.powerOff() }
                MenuItem { text: "Restart"; enabled: sddm.canReboot; onTriggered: sddm.reboot() }
            }
        }
    }

    component Corner: MouseArea {
        id: corner
        property string icon
        property string label: ""
        width: label ? labelText.implicitWidth + 56 * root.s : 44 * root.s
        height: 44 * root.s
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        Rectangle {
            anchors.fill: parent
            radius: 6 * root.s
            color: corner.pressed ? "#40ffffff" : (corner.containsMouse ? "#28ffffff" : "transparent")
        }
        Row {
            anchors.centerIn: parent
            spacing: 8 * root.s
            Image {
                anchors.verticalCenter: parent.verticalCenter
                source: corner.icon
                width: 24 * root.s
                height: width
                sourceSize: Qt.size(width * 2, height * 2)
            }
            Text {
                id: labelText
                anchors.verticalCenter: parent.verticalCenter
                visible: corner.label !== ""
                text: corner.label
                color: "white"
                font.family: root.fontName
                font.pixelSize: 15 * root.s
            }
        }
    }

    // the lock screen goes on any key or click
    MouseArea {
        anchors.fill: parent
        enabled: root.locked
        visible: root.locked
        onClicked: root.unlock()
    }
    focus: true
    Keys.onPressed: function (event) {
        if (root.locked) {
            root.unlock()
            // the first letter typed goes into the password, like windows
            if (event.text && event.text.trim() !== "" && event.key !== Qt.Key_Space) password.insert(0, event.text)
            event.accepted = true
        }
    }
    Component.onCompleted: locked ? forceActiveFocus() : password.forceActiveFocus()
}
