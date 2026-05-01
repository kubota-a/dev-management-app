(function () {
    var DESKTOP_BREAKPOINT = "(min-width: 900px)";
  
    function setModalState(modal, isOpen) {
      modal.classList.toggle("is-open", isOpen);
      modal.setAttribute("aria-hidden", isOpen ? "false" : "true");
    }
  
    function closeAllModals() {
      document.querySelectorAll(".modal-overlay.is-open").forEach(function (modal) {
        setModalState(modal, false);
      });
    }
  
    function getDrawerElements() {
      return {
        drawer: document.getElementById("mobileDrawer"),
        overlay: document.getElementById("mobileDrawerOverlay"),
        openButtons: document.querySelectorAll("[data-drawer-open]")
      };
    }
  
    function setDrawerState(isOpen) {
      var drawerUI = getDrawerElements();
      var drawer = drawerUI.drawer;
      var overlay = drawerUI.overlay;
  
      if (!drawer || !overlay) return;
  
      drawer.classList.toggle("is-open", isOpen);
      overlay.classList.toggle("is-open", isOpen);
      drawer.setAttribute("aria-hidden", isOpen ? "false" : "true");
      document.body.classList.toggle("is-drawer-open", isOpen);
  
      drawerUI.openButtons.forEach(function (button) {
        button.setAttribute("aria-expanded", isOpen ? "true" : "false");
      });
    }
  
    function bindDrawerBreakpointReset() {
      var media = window.matchMedia(DESKTOP_BREAKPOINT);
  
      function onViewportChange(event) {
        if (event.matches) {
          setDrawerState(false);
        }
      }
  
      if (typeof media.addEventListener === "function") {
        media.addEventListener("change", onViewportChange);
      } else {
        media.addListener(onViewportChange);
      }
  
      if (media.matches) {
        setDrawerState(false);
      }
    }
  
    function getAccountMenuRoots() {
      return document.querySelectorAll("[data-account-menu-root]");
    }
  
    function getAccountMenuElements(root) {
      if (!root) return {};
  
      return {
        root: root,
        toggle: root.querySelector("[data-account-menu-toggle]"),
        menu: root.querySelector("[data-account-menu]")
      };
    }
  
    function isAccountMenuOpen(root) {
      var accountMenuUI = getAccountMenuElements(root);
      return !!(accountMenuUI.menu && accountMenuUI.menu.classList.contains("is-open"));
    }
  
    function setAccountMenuState(root, isOpen) {
      var accountMenuUI = getAccountMenuElements(root);
  
      if (!accountMenuUI.toggle || !accountMenuUI.menu) return;
  
      accountMenuUI.menu.classList.toggle("is-open", isOpen);
      accountMenuUI.toggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
      accountMenuUI.menu.setAttribute("aria-hidden", isOpen ? "false" : "true");
    }
  
    function closeAllAccountMenus() {
      getAccountMenuRoots().forEach(function (root) {
        setAccountMenuState(root, false);
      });
    }

    function getNotificationRoots() {
      return document.querySelectorAll("[data-notification-root]");
    }

    function getNotificationElements(root) {
      if (!root) return {};

      return {
        root: root,
        toggle: root.querySelector("[data-notification-toggle]"),
        dropdown: root.querySelector("[data-notification-dropdown]"),
        title: root.querySelector("[data-notification-title]")
      };
    }

    function isNotificationOpen(root) {
      var notificationUI = getNotificationElements(root);
      return !!(notificationUI.dropdown && notificationUI.dropdown.classList.contains("is-open"));
    }

    function setNotificationState(root, isOpen) {
      var notificationUI = getNotificationElements(root);
      if (!notificationUI.toggle || !notificationUI.dropdown) return;

      notificationUI.dropdown.classList.toggle("is-open", isOpen);
      notificationUI.toggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
      notificationUI.dropdown.setAttribute("aria-hidden", isOpen ? "false" : "true");
    }

    function closeAllNotifications() {
      getNotificationRoots().forEach(function (root) {
        setNotificationState(root, false);
      });
    }

    function markAllNotificationsAsRead(root) {
      var notificationUI = getNotificationElements(root);
      if (!notificationUI.root) return;

      notificationUI.root.querySelectorAll(".notification-item.is-unread").forEach(function (item) {
        item.classList.remove("is-unread");
        var dot = item.querySelector(".notification-dot");
        if (dot) {
          dot.classList.add("notification-dot-read");
        }
      });

      notificationUI.root.querySelectorAll(".header-notification-badge, .header-notification-badge-text").forEach(function (badge) {
        badge.setAttribute("hidden", "hidden");
        badge.style.display = "none";
      });

      if (notificationUI.title) {
        notificationUI.title.textContent = "通知（全て既読）";
      }

      if (notificationUI.toggle) {
        notificationUI.toggle.setAttribute("aria-label", "通知 0 件");
      }
    }
  
    var FLASH_CLASS_MAP = {
      success: "alert-success",
      warning: "alert-warning",
      danger: "alert-danger",
      info: "alert-info",
      notice: "alert-info"
    };
  
    function getFlashElements() {
      var region = document.getElementById("flashRegion") || document.getElementById("flashDemoRegion");
      var alert = document.getElementById("flashAlert") || document.getElementById("flashDemoAlert");
      var text = document.getElementById("flashText") || document.getElementById("flashDemoText");

      return {
        region: region,
        alert: alert,
        text: text
      };
    }
  
    function showFlash(type, message) {
      var flash = getFlashElements();
      if (!flash.region || !flash.alert || !flash.text) return;
  
      var tone = FLASH_CLASS_MAP[type] ? type : "info";
  
      flash.alert.classList.remove("alert-success", "alert-warning", "alert-danger", "alert-info", "alert-notice");
      flash.alert.classList.add(FLASH_CLASS_MAP[tone]);
      flash.text.textContent = message;
      flash.alert.setAttribute("role", tone === "danger" ? "alert" : "status");
      flash.region.hidden = false;
    }
  
    function hideFlash() {
      var flash = getFlashElements();
      if (!flash.region) return;
  
      flash.region.hidden = true;
    }

    function bindLoginPasswordToggle() {
      var passwordInput = document.getElementById("login-password");
      var toggleButton = document.querySelector(".login-password-toggle");

      if (!passwordInput || !toggleButton) return;

      toggleButton.addEventListener("click", function () {
        passwordInput.type = passwordInput.type === "password" ? "text" : "password";
      });
    }

    function bindToastAutoHide() {
      document.querySelectorAll("[data-toast-message]").forEach(function (toast) {
        window.setTimeout(function () {
          toast.classList.add("is-hidden");
          window.setTimeout(function () {
            if (toast && toast.parentNode) {
              toast.parentNode.removeChild(toast);
            }
          }, 220);
        }, 2600);
      });
    }
  
    document.addEventListener("click", function (event) {
      var notificationToggle = event.target.closest("[data-notification-toggle]");
      var notificationMarkAll = event.target.closest("[data-notification-mark-all]");
      var clickedNotificationRoot = event.target.closest("[data-notification-root]");
      var accountMenuToggle = event.target.closest("[data-account-menu-toggle]");
      var accountMenuItem = event.target.closest("[data-account-menu-item]");
      var clickedAccountMenuRoot = event.target.closest("[data-account-menu-root]");

      if (notificationToggle) {
        var notificationRoot = notificationToggle.closest("[data-notification-root]");
        var shouldOpenNotification = !isNotificationOpen(notificationRoot);
        closeAllNotifications();
        closeAllAccountMenus();
        setNotificationState(notificationRoot, shouldOpenNotification);
        return;
      }

      if (notificationMarkAll) {
        var markAllRoot = notificationMarkAll.closest("[data-notification-root]");
        markAllNotificationsAsRead(markAllRoot);
        return;
      }

      if (accountMenuToggle) {
        var toggleRoot = accountMenuToggle.closest("[data-account-menu-root]");
        var shouldOpen = !isAccountMenuOpen(toggleRoot);
        closeAllNotifications();
        closeAllAccountMenus();
        setAccountMenuState(toggleRoot, shouldOpen);
        return;
      }
  
      if (accountMenuItem) {
        var itemRoot = accountMenuItem.closest("[data-account-menu-root]");
        setAccountMenuState(itemRoot, false);
        return;
      }
  
      if (!clickedAccountMenuRoot) {
        closeAllAccountMenus();
      }

      if (!clickedNotificationRoot) {
        closeAllNotifications();
      }
  
      var flashShowTrigger = event.target.closest("[data-flash-show]");
      if (flashShowTrigger) {
        showFlash(
          flashShowTrigger.getAttribute("data-flash-show"),
          flashShowTrigger.getAttribute("data-flash-message") || "Message displayed."
        );
        return;
      }
  
      var flashCloseTrigger = event.target.closest("[data-flash-close]");
      if (flashCloseTrigger) {
        hideFlash();
        return;
      }
  
      var openTrigger = event.target.closest("[data-modal-open]");
      if (openTrigger) {
        var modalId = openTrigger.getAttribute("data-modal-open");
        var targetModal = document.getElementById(modalId);
        if (targetModal && targetModal.classList.contains("modal-overlay")) {
          setModalState(targetModal, true);
        }
        return;
      }
  
      var closeTrigger = event.target.closest("[data-modal-close]");
      if (closeTrigger) {
        var parentModal = closeTrigger.closest(".modal-overlay");
        if (parentModal) {
          setModalState(parentModal, false);
        } else {
          closeAllModals();
        }
        return;
      }
  
      var drawerOpenTrigger = event.target.closest("[data-drawer-open]");
      if (drawerOpenTrigger) {
        setDrawerState(true);
        return;
      }
  
      var drawerCloseTrigger = event.target.closest("[data-drawer-close]");
      if (drawerCloseTrigger) {
        setDrawerState(false);
        return;
      }
  
      if (event.target.classList.contains("modal-overlay")) {
        setModalState(event.target, false);
      }
    });
  
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        closeAllModals();
        setDrawerState(false);
        closeAllAccountMenus();
        closeAllNotifications();
      }
    });

    bindLoginPasswordToggle();
    bindToastAutoHide();
    bindDrawerBreakpointReset();
  })();
  
