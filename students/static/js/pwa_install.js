let deferredPrompt;

window.addEventListener('beforeinstallprompt', (e) => {
  // Prevent the mini-infobar from appearing on mobile
  e.preventDefault();
  // Stash the event so it can be triggered later.
  deferredPrompt = e;

  // Show the install UI
  const installBanner = document.getElementById('pwaInstallBanner');
  if (installBanner) {
      installBanner.style.display = 'flex';
  }
});

async function installPWA() {
  if (deferredPrompt) {
    deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    console.log(`User response to the install prompt: ${outcome}`);
    deferredPrompt = null;

    // Hide banner
    document.getElementById('pwaInstallBanner').style.display = 'none';
  }
}

function dismissInstall() {
    document.getElementById('pwaInstallBanner').style.display = 'none';
}
