import { initializeApp } from "https://www.gstatic.com/firebasejs/12.19.0/firebase-app.js";
import {
    getAuth,
    createUserWithEmailAndPassword,
    signInWithEmailAndPassword,
    signInWithPopup,
    GoogleAuthProvider,
    updateProfile
} from "https://www.gstatic.com/firebasejs/12.19.0/firebase-auth.js";

import { firebaseConfig } from "./firebase-config.js";

const API_URL = "http://localhost:8010";

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const googleProvider = new GoogleAuthProvider();

googleProvider.setCustomParameters({
    prompt: "select_account"
});

const authForm = document.getElementById("authForm");
const authTitle = document.getElementById("authTitle");
const authSubtitle = document.getElementById("authSubtitle");
const authSubmitButton = document.getElementById("authSubmitButton");
const authSwitchQuestion = document.getElementById("authSwitchQuestion");
const authSwitchButton = document.getElementById("authSwitchButton");
const authMessage = document.getElementById("authMessage");
const googleButton = document.getElementById("googleButton");

const nameField = document.getElementById("nameField");
const nameInput = document.getElementById("name");
const emailInput = document.getElementById("email");
const passwordInput = document.getElementById("password");

let isRegisterMode = false;

function showMessage(message, type = "error") {
    if (!authMessage) {
        alert(message);
        return;
    }

    authMessage.textContent = message;
    authMessage.className = `auth-message ${type}`;
}

function setLoading(isLoading) {
    if (authSubmitButton) {
        authSubmitButton.disabled = isLoading;
        authSubmitButton.textContent = isLoading
            ? "Please wait..."
            : isRegisterMode
                ? "Create account"
                : "Sign in";
    }

    if (googleButton) {
        googleButton.disabled = isLoading;
    }
}

function switchMode() {
    isRegisterMode = !isRegisterMode;

    if (nameField) {
        nameField.classList.toggle("hidden", !isRegisterMode);
    }

    if (authTitle) {
        authTitle.textContent = isRegisterMode
            ? "Create your workspace account"
            : "Sign in to your workspace";
    }

    if (authSubtitle) {
        authSubtitle.textContent = isRegisterMode
            ? "Add your name so MicroManager can personalise the dashboard."
            : "Enter your details to continue.";
    }

    if (authSubmitButton) {
        authSubmitButton.textContent = isRegisterMode
            ? "Create account"
            : "Sign in";
    }

    if (authSwitchQuestion) {
        authSwitchQuestion.textContent = isRegisterMode
            ? "Already have an account?"
            : "Don’t have an account?";
    }

    if (authSwitchButton) {
        authSwitchButton.textContent = isRegisterMode
            ? "Sign in"
            : "Create account";
    }

    if (passwordInput) {
        passwordInput.autocomplete = isRegisterMode
            ? "new-password"
            : "current-password";
    }

    if (authMessage) {
        authMessage.textContent = "";
    }
}

function getNameFromEmail(email) {
    if (!email) {
        return "User";
    }

    return email
        .split("@")[0]
        .replace(/[._-]+/g, " ")
        .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

async function syncBackendProfile(user) {
    const name =
        user.displayName ||
        getNameFromEmail(user.email);

    const email = user.email || "";

    localStorage.setItem("microManagerLoggedIn", "true");
    localStorage.setItem("microManagerUserName", name);
    localStorage.setItem("microManagerUserEmail", email);

    try {
        await fetch(`${API_URL}/users/me`, {
            method: "PUT",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                name: name,
                email: email,
                role: "Team member"
            })
        });
    } catch (error) {
        console.warn("Could not sync backend profile yet:", error);
    }
}

async function goToDashboard(user) {
    await syncBackendProfile(user);
    window.location.href = "index.html";
}

if (authSwitchButton) {
    authSwitchButton.addEventListener("click", switchMode);
}

if (authForm) {
    authForm.addEventListener("submit", async (event) => {
        event.preventDefault();

        const name = nameInput ? nameInput.value.trim() : "";
        const email = emailInput ? emailInput.value.trim() : "";
        const password = passwordInput ? passwordInput.value : "";

        if (isRegisterMode && !name) {
            showMessage("Please enter your name.");
            return;
        }

        setLoading(true);

        try {
            if (isRegisterMode) {
                const result = await createUserWithEmailAndPassword(
                    auth,
                    email,
                    password
                );

                await updateProfile(result.user, {
                    displayName: name
                });

                await goToDashboard(result.user);
                return;
            }

            const result = await signInWithEmailAndPassword(
                auth,
                email,
                password
            );

            await goToDashboard(result.user);
        } catch (error) {
            console.error(error);
            showMessage(error.message || "Authentication failed.");
        } finally {
            setLoading(false);
        }
    });
}

if (googleButton) {
    googleButton.addEventListener("click", async () => {
        console.log("Google button clicked");

        setLoading(true);
        showMessage("Opening Google sign in...", "info");

        try {
            const result = await signInWithPopup(auth, googleProvider);
            await goToDashboard(result.user);
        } catch (error) {
            console.error(error);

            if (error.code === "auth/popup-blocked") {
                showMessage("Popup blocked. Allow popups for localhost and try again.");
            } else if (error.code === "auth/popup-closed-by-user") {
                showMessage("Google sign in was closed before finishing.");
            } else if (error.code === "auth/unauthorized-domain") {
                showMessage("Add localhost and 127.0.0.1 to Firebase authorized domains.");
            } else if (error.code === "auth/operation-not-allowed") {
                showMessage("Enable Google provider in Firebase Authentication.");
            } else {
                showMessage(error.message || "Google sign in failed.");
            }
        } finally {
            setLoading(false);
        }
    });
} else {
    console.error("Google button was not found in login.html");
}