import {
    onAuthStateChanged,
    signOut
} from "https://www.gstatic.com/firebasejs/12.19.0/firebase-auth.js";

import {
    auth
} from "./firebase-config.js";


document.documentElement.style.visibility =
    "hidden";


onAuthStateChanged(
    auth,
    user => {

        if (!user) {

            window.location.replace(
                "login.html"
            );

            return;

        }


        document.documentElement.style.visibility =
            "visible";


        const name =
            user.displayName ||
            user.email?.split("@")[0] ||
            "User";


        const initial =
            name.charAt(0).toUpperCase();


        const profileName =
            document.getElementById(
                "profileName"
            );


        const profileInitial =
            document.getElementById(
                "profileInitial"
            );


        const topAvatarInitial =
            document.getElementById(
                "topAvatarInitial"
            );


        if (profileName) {

            profileName.textContent =
                name;

        }


        if (profileInitial) {

            profileInitial.textContent =
                initial;

        }


        if (topAvatarInitial) {

            topAvatarInitial.textContent =
                initial;

        }


        console.log(
            "Logged in as:",
            user.email
        );

    }
);


const logoutButton =
    document.getElementById(
        "logoutButton"
    );


if (logoutButton) {

    logoutButton.addEventListener(
        "click",
        async event => {

            event.preventDefault();

            event.stopImmediatePropagation();


            try {

                await signOut(auth);

                window.location.replace(
                    "login.html"
                );

            } catch (error) {

                console.error(error);

                alert(
                    "Could not log out."
                );

            }

        },
        true
    );

}