(function () {
    var box = document.getElementById("is_publicbox");
    if (box) {
        var label = box.parentElement.querySelector(".toggle__label");
        if (label) {
            box.addEventListener("change", function () {
                label.textContent = box.checked ? "Público" : "Privado";
            });
        }
    }

    var done = document.getElementById("donebox");
    if (done) {
        var doneLabel = done.parentElement.querySelector(".toggle__label");
        if (doneLabel) {
            done.addEventListener("change", function () {
                doneLabel.textContent = done.checked ? "Ya regalado" : "Pendiente";
            });
        }
    }
})();