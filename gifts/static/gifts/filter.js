(function () {
    var input = document.getElementById("person-filter-search");
    if (!input) return;
    var form = document.getElementById("person-filter-form");
    if (!form) return;
    var empty = document.getElementById("person-filter-empty");
    var pills = Array.prototype.slice.call(form.querySelectorAll(".person-pill"));

    input.addEventListener("input", function () {
        var term = input.value.trim().toLowerCase();
        var visible = 0;
        pills.forEach(function (pill) {
            var matches = pill.textContent.toLowerCase().indexOf(term) !== -1;
            pill.classList.toggle("filter-hidden", !matches);
            if (matches) visible += 1;
        });
        if (empty) empty.hidden = visible !== 0;
    });
})();