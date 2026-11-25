document.addEventListener("DOMContentLoaded", function () {
    const menuButton = document.getElementById("menu-button");
    const slidingMenu = document.getElementById("sliding-menu");

    function setMenu(open) {
        if (!slidingMenu || !menuButton) {
            return;
        }
        slidingMenu.classList.toggle("open", open);
        menuButton.classList.toggle("open", open);
        menuButton.setAttribute("aria-expanded", open ? "true" : "false");
        document.body.classList.toggle("menu-open", open);
        if (!open) {
            slidingMenu.querySelectorAll(".kata-dropdown.open").forEach(function (item) {
                item.classList.remove("open");
                const trigger = item.querySelector("a");
                if (trigger) {
                    trigger.setAttribute("aria-expanded", "false");
                }
            });
        }
    }

    if (menuButton && slidingMenu) {
        menuButton.setAttribute("aria-label", "Menu");
        menuButton.setAttribute("aria-expanded", "false");
        menuButton.addEventListener("click", function () {
            setMenu(!slidingMenu.classList.contains("open"));
        });
    }

    document.querySelectorAll(".kata-dropdown > a").forEach(function (trigger) {
        trigger.setAttribute("role", "button");
        trigger.setAttribute("aria-expanded", "false");
        trigger.addEventListener("click", function (event) {
            event.preventDefault();
            const item = trigger.parentElement;
            const open = !item.classList.contains("open");
            document.querySelectorAll(".kata-dropdown.open").forEach(function (other) {
                if (other === item) {
                    return;
                }
                other.classList.remove("open");
                const otherTrigger = other.querySelector("a");
                if (otherTrigger) {
                    otherTrigger.setAttribute("aria-expanded", "false");
                }
            });
            item.classList.toggle("open", open);
            trigger.setAttribute("aria-expanded", open ? "true" : "false");
        });
    });

    if (slidingMenu) {
        slidingMenu.addEventListener("click", function (event) {
            const link = event.target.closest("a");
            if (!link || link.getAttribute("href") === "#") {
                return;
            }
            setMenu(false);
        });
    }
});
