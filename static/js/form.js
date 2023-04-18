const password = document.querySelector("input#password");
const confirmPassword = document.querySelector("input#confirm-password");

if (password !== null && confirmPassword !== null) {
    confirmPassword.addEventListener('input', (_) => {
        if (password.value != confirmPassword.value) {
            password.setCustomValidity("Passwords don't match.");
            confirmPassword.setCustomValidity("Passwords don't match.");
            password.setAttribute("title", "Passwords don't match.");
            confirmPassword.setAttribute("title", "Passwords don't match.");
        } else {
            password.setCustomValidity("");
            confirmPassword.setCustomValidity("");
            password.setAttribute("title", "");
            confirmPassword.setAttribute("title", "");
        }
    })
}


const child_enablers = document.querySelectorAll("input.enable-next");

if (child_enablers !== null) {
    setInterval(() => {
        for (const element of child_enablers) {
            if (element.checked) {
                element.nextElementSibling.disabled = false;
                element.nextElementSibling.children[0].children[0].required = true;
            } else {
                element.nextElementSibling.disabled = true;
                element.nextElementSibling.children[0].children[0].required = false;
            }
        }
    }, 100);
}

if ( window.history.replaceState ) {
    window.history.replaceState( null, null, window.location.href );
}
