document.addEventListener("DOMContentLoaded", function () {
    const menuButton = document.getElementById("menu-button");
    const slidingMenu = document.getElementById("sliding-menu");
    const closeButton = document.querySelector(".close");

    if (menuButton && slidingMenu) {
        menuButton.setAttribute("aria-label", "Menu");
        menuButton.setAttribute("aria-expanded", "false");
        menuButton.addEventListener("click", function () {
            const open = slidingMenu.classList.toggle("open");
            menuButton.classList.toggle("open", open);
            menuButton.setAttribute("aria-expanded", open ? "true" : "false");
        });
    }

    if (closeButton && slidingMenu) {
        closeButton.addEventListener("click", function () {
            slidingMenu.classList.remove("open");
        });
    }
});
