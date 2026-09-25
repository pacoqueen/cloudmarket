(function () {
    var input = document.getElementById("id_url");
    if (!input) {
        return;
    }

    var link = document.querySelector("[data-url-open]");
    if (!link) {
        link = document.createElement("a");
        link.className = "gift-add__open-link";
        link.setAttribute("data-url-open", "");
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.title = "Abrir en una pestaña nueva";
        link.setAttribute("aria-label", "Abrir el enlace del artículo en una pestaña nueva");
        link.innerHTML = '<span aria-hidden="true">↗</span> Abrir';
        input.parentNode.appendChild(link);
    }

    function normalize(value) {
        value = value.trim();
        if (!value) {
            return "";
        }
        if (!/^[a-z][a-z0-9+.-]*:/i.test(value)) {
            return "https://" + value;
        }
        return value;
    }

    function sync() {
        var href = normalize(input.value);
        if (!href) {
            link.hidden = true;
            return;
        }
        link.href = href;
        link.hidden = false;
    }

    input.addEventListener("input", sync);
    input.addEventListener("change", sync);
    sync();
})();
