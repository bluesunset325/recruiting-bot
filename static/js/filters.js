(function () {
    const form = document.getElementById("filter-form");
    if (!form) return;

    let debounceTimer = null;

    function submitForm() {
        form.submit();
    }

    function debounceSubmit() {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(submitForm, 400);
    }

    form.querySelectorAll("select").forEach(function (el) {
        el.addEventListener("change", submitForm);
    });

    // поиск по тексту — с задержкой 400 мс
    form.querySelectorAll("input[type='text'], input[type='number']").forEach(function (el) {
        el.addEventListener("input", debounceSubmit);
    });
})();
