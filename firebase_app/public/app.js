// Initialize Firebase
const firebaseConfig = {
    // IMPORTANT: REPLACE THIS WITH YOUR FIREBASE WEB CONFIG
    // Go to Firebase Console -> Project Settings -> General -> Your apps -> Web app -> Config
    apiKey: "YOUR_API_KEY",
    authDomain: "YOUR_PROJECT_ID.firebaseapp.com",
    projectId: "YOUR_PROJECT_ID",
    storageBucket: "YOUR_PROJECT_ID.appspot.com",
    messagingSenderId: "YOUR_SENDER_ID",
    appId: "YOUR_APP_ID"
};

// Initialize Firebase
if (!firebase.apps.length) {
    firebase.initializeApp(firebaseConfig);
} else {
    firebase.app(); // if already initialized, use that one
}

const db = firebase.firestore();
const auth = firebase.auth();

console.log("Firebase Initialized");
