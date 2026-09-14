import {
    initializeApp,
    getApp,
    getApps
} from "https://www.gstatic.com/firebasejs/12.19.0/firebase-app.js";

import {
    getAuth,
    onAuthStateChanged,
    signOut
} from "https://www.gstatic.com/firebasejs/12.19.0/firebase-auth.js";

import {
    firebaseConfig
} from "./firebase-config.js";


const app = getApps().length > 0
    ? getApp()
    : initializeApp(firebaseConfig);

const auth = getAuth(app);


document.documentElement.style.visibility = "hidden";


onAuthStateChanged(auth, user => {

    if (!user) {

        localStorage.removeItem("microManagerLoggedIn");
        localStorage.removeItem("microManagerUserName");
        localStorage.removeItem("microManagerUserEmail");

        window.location.replace("login.html");
        return;

    }

    const name =
        user.displayName ||
        user.email?.split("@")[0] ||
        "User";

    const email = user.email || "";

    localStorage.setItem("microManagerLoggedIn", "true");
    localStorage.setItem("microManagerUserName", name);
    localStorage.setItem("microManagerUserEmail", email);

    const initial =
        name.trim().charAt(0).toUpperCase() || "U";

    setText("profileName", name);
    setText("profileInitial", initial);
    setText("topAvatarInitial", initial);
    setText("largeProfileInitial", initial);
    setText("profilePageName", name);
    setText("greetingName", name.split(" ")[0]);

    document.documentElement.style.visibility = "visible";

    console.log("Logged in as:", email);

});


const logoutButton = document.getElementById("logoutButton");

if (logoutButton) {

    logoutButton.addEventListener(
        "click",
        async event => {

            event.preventDefault();
            event.stopImmediatePropagation();

            try {

                await signOut(auth);

                localStorage.removeItem("microManagerLoggedIn");
                localStorage.removeItem("microManagerUserName");
                localStorage.removeItem("microManagerUserEmail");
                localStorage.removeItem("microManagerWorkspace");

                window.location.replace("login.html");

            } catch (error) {

                console.error("Logout failed:", error);
                alert("Could not log out. Please try again.");

            }

        },
        true
    );

}


function setText(id, value) {

    const element = document.getElementById(id);

    if (element) {
        element.textContent = value;
    }

}