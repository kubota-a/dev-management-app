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

    function escapeNotificationText(value) {
      return String(value || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
    }

    function buildNotificationItemHtml(notification) {
      return (
        '<div class="notification-item is-unread" data-notification-item data-notification-id="' + notification.id + '">' +
          '<span class="notification-dot" aria-hidden="true"></span>' +
          '<div class="notification-body">' +
            '<div class="notification-message"><strong>' + escapeNotificationText(notification.project_title) + "</strong></div>" +
            '<div class="notification-message">' + escapeNotificationText(notification.message) + "</div>" +
            '<div class="notification-time">' + escapeNotificationText(notification.created_at_label) + "</div>" +
          "</div>" +
        "</div>"
      );
    }

    function renderNotificationDropdown(root, unreadCount, notifications) {
      var notificationUI = getNotificationElements(root);
      if (!notificationUI.root || !notificationUI.dropdown) return;
      var safeUnreadCount = Number(unreadCount) || 0;
      var safeNotifications = Array.isArray(notifications) ? notifications : [];
      var listContainer = notificationUI.dropdown.querySelector("[data-notification-list]");
      var markButton = notificationUI.dropdown.querySelector("[data-notification-mark-all]");

      if (safeUnreadCount > 0) {
        if (notificationUI.title) {
          notificationUI.title.textContent = "通知（" + safeUnreadCount + "件未読）";
        }
        if (!markButton) {
          var head = notificationUI.dropdown.querySelector(".notification-dropdown-head");
          if (head) {
            markButton = document.createElement("button");
            markButton.type = "button";
            markButton.className = "notification-mark-all";
            markButton.setAttribute("data-notification-mark-all", "1");
            markButton.textContent = "表示中を既読";
            head.appendChild(markButton);
          }
        } else {
          markButton.textContent = "表示中を既読";
        }
      } else {
        if (notificationUI.title) {
          notificationUI.title.textContent = "未読なし";
        }
        if (markButton && markButton.parentNode) {
          markButton.parentNode.removeChild(markButton);
        }
      }

      if (!listContainer) {
        listContainer = document.createElement("div");
        listContainer.setAttribute("data-notification-list", "1");
        notificationUI.dropdown.appendChild(listContainer);
      }

      if (safeNotifications.length > 0) {
        listContainer.innerHTML = safeNotifications.map(buildNotificationItemHtml).join("");
        listContainer.hidden = false;
      } else {
        listContainer.innerHTML = "";
        listContainer.hidden = true;
      }

      if (notificationUI.toggle) {
        notificationUI.toggle.setAttribute("aria-label", "通知 " + safeUnreadCount + " 件");
      }

      notificationUI.root.querySelectorAll(".header-notification-badge, .header-notification-badge-text").forEach(function (badge) {
        if (safeUnreadCount > 0) {
          badge.removeAttribute("hidden");
          badge.style.display = "";
          if (badge.classList.contains("header-notification-badge-text")) {
            badge.textContent = safeUnreadCount < 10 ? String(safeUnreadCount) : "9+";
          }
        } else {
          badge.setAttribute("hidden", "hidden");
          badge.style.display = "none";
        }
      });
    }

    function markVisibleNotificationsAsRead(root) {
      var notificationUI = getNotificationElements(root);
      if (!notificationUI.root) return;

      var markButton = notificationUI.root.querySelector("[data-notification-mark-all]");
      var visibleIds = [];
      notificationUI.root.querySelectorAll("[data-notification-item][data-notification-id]").forEach(function (item) {
        var rawId = item.getAttribute("data-notification-id");
        var parsedId = Number(rawId);
        if (Number.isInteger(parsedId) && parsedId > 0) {
          visibleIds.push(parsedId);
        }
      });

      if (!visibleIds.length) {
        return;
      }

      if (markButton) {
        markButton.disabled = true;
      }

      var requestUrl = notificationUI.root.getAttribute("data-mark-visible-read-url");
      var csrfToken = notificationUI.root.getAttribute("data-csrf-token");
      fetch(requestUrl, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken || ""
        },
        body: JSON.stringify({ notification_ids: visibleIds })
      })
        .then(function (response) {
          return response.json().then(function (data) {
            return { ok: response.ok, data: data };
          });
        })
        .then(function (result) {
          if (!result.ok || !result.data || !result.data.ok) {
            throw new Error("mark_visible_read_failed");
          }
          renderNotificationDropdown(notificationUI.root, result.data.unread_count, result.data.notifications);
        })
        .catch(function () {
          if (typeof window.showApplicantProgressToast === "function") {
            window.showApplicantProgressToast("通知の既読処理に失敗しました。");
          } else {
            window.alert("通知の既読処理に失敗しました。");
          }
        })
        .finally(function () {
          if (markButton) {
            markButton.disabled = false;
          }
        });
    }

    function bindInitialNotificationState() {
      getNotificationRoots().forEach(function (root) {
        var notificationUI = getNotificationElements(root);
        if (!notificationUI.root) return;
        var unreadText = notificationUI.toggle ? (notificationUI.toggle.getAttribute("aria-label") || "").match(/[0-9]+/) : null;
        var unreadCount = unreadText ? Number(unreadText[0]) : 0;
        var notifications = [];
        notificationUI.root.querySelectorAll("[data-notification-item]").forEach(function (item) {
          var rawId = item.getAttribute("data-notification-id");
          var titleEl = item.querySelector(".notification-message strong");
          var messageEls = item.querySelectorAll(".notification-message");
          var timeEl = item.querySelector(".notification-time");
          var messageText = messageEls.length > 1 ? messageEls[1].textContent : "";
          notifications.push({
            id: Number(rawId) || 0,
            project_title: titleEl ? titleEl.textContent : "",
            message: messageText || "",
            created_at_label: timeEl ? timeEl.textContent : ""
          });
        });
        renderNotificationDropdown(notificationUI.root, unreadCount, notifications);
      });
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
        markVisibleNotificationsAsRead(markAllRoot);
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
    bindInitialNotificationState();
  })();
  
