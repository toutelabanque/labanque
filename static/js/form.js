const password = document.getElementById("password");
const confirmPassword = document.getElementById("confirm-password");

console.log(password)
console.log(confirmPassword)

if (password !== null && confirmPassword !== null) {
    console.log("not null")
    confirmPassword.addEventListener('blur', (_) => {
        if (password.value != confirmPassword.value) {
            password.setCustomValidity("Passwords don't match.")
            confirmPassword.setCustomValidity("Passwords don't match.")
            password.setAttribute("title", "Passwords don't match.")
            confirmPassword.setAttribute("title", "Passwords don't match.")
        } else {
            password.setCustomValidity("")
            confirmPassword.setCustomValidity("")
            password.setAttribute("title", "")
            confirmPassword.setAttribute("title", "")
        }
    })
}
