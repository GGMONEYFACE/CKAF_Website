document.addEventListener("DOMContentLoaded", function () {
    const menuButton = document.getElementById("menu-button");
    const slidingMenu = document.getElementById("sliding-menu");
    const closeButton = document.querySelector(".close");

    if (menuButton && slidingMenu) {
        menuButton.addEventListener("click", function () {
            slidingMenu.classList.toggle("open");
        });
    }

    if (closeButton && slidingMenu) {
        closeButton.addEventListener("click", function () {
            slidingMenu.classList.remove("open");
        });
    }
});
