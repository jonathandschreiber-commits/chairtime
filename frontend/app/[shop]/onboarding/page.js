"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import styles from "./onboarding.module.css";

const API_BASE =
  "https://chairtime-production-94da.up.railway.app";

const DAYS = [
  { name: "Monday", weekday: 0 },
  { name: "Tuesday", weekday: 1 },
  { name: "Wednesday", weekday: 2 },
  { name: "Thursday", weekday: 3 },
  { name: "Friday", weekday: 4 },
  { name: "Saturday", weekday: 5 },
  { name: "Sunday", weekday: 6 },
];

function makeDefaultHours() {
  return DAYS.map((day) => ({
    ...day,
    open: day.weekday <= 4,
    start: "09:00",
    end: "17:00",
  }));
}

export default function OnboardingPage() {
  const params = useParams();
  const router = useRouter();

  const shopSlug = params.shop;

  const [hours, setHours] = useState(
    makeDefaultHours()
  );

  const [existingRules, setExistingRules] =
    useState([]);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  const openDayCount = useMemo(() => {
    return hours.filter((day) => day.open).length;
  }, [hours]);

  useEffect(() => {
    if (!shopSlug) return;

    loadHours();
  }, [shopSlug]);

  async function loadHours() {
    setLoading(true);
    setMessage("");

    try {
      const response = await fetch(
        `${API_BASE}/api/shop-availability-rules?shop_slug=${encodeURIComponent(
          shopSlug
        )}`,
        {
          cache: "no-store",
        }
      );

      if (!response.ok) {
        throw new Error(
          "Could not load your shop hours."
        );
      }

      const data = await response.json();

      setExistingRules(data);

      if (data.length > 0) {
        setHours(
          DAYS.map((day) => {
            const rule = data.find(
              (item) =>
                item.weekday === day.weekday
            );

            if (!rule) {
              return {
                ...day,
                open: false,
                start: "09:00",
                end: "17:00",
              };
            }

            return {
              ...day,
              open: true,
              start: String(
                rule.start_time
              ).slice(0, 5),
              end: String(
                rule.end_time
              ).slice(0, 5),
            };
          })
        );
      }
    } catch (error) {
      console.error(error);

      setMessage(
        error instanceof Error
          ? error.message
          : "Could not load your shop hours."
      );
    } finally {
      setLoading(false);
    }
  }

  function updateDay(
    weekday,
    field,
    value
  ) {
    setHours((current) =>
      current.map((day) =>
        day.weekday === weekday
          ? {
              ...day,
              [field]: value,
            }
          : day
      )
    );

    setMessage("");
  }

  async function saveHours() {
    if (saving) return;

    const invalidDay = hours.find(
      (day) =>
        day.open &&
        (!day.start ||
          !day.end ||
          day.start >= day.end)
    );

    if (invalidDay) {
      setMessage(
        `${invalidDay.name}: closing time must be later than opening time.`
      );

      return;
    }

    if (openDayCount === 0) {
      setMessage(
        "Choose at least one day your business is open."
      );

      return;
    }

    setSaving(true);
    setMessage("");

    try {
      /*
       * Remove existing shop-wide hours first.
       * This keeps onboarding simple:
       * what the owner sees on this screen
       * becomes the complete weekly schedule.
       */
      for (const rule of existingRules) {
        const deleteResponse = await fetch(
          `${API_BASE}/api/shop-availability-rules/${encodeURIComponent(
            rule.id
          )}`,
          {
            method: "DELETE",
          }
        );

        if (!deleteResponse.ok) {
          throw new Error(
            "Could not update your shop hours."
          );
        }
      }

      /*
       * Save each open day.
       */
      for (const day of hours) {
        if (!day.open) continue;

        const response = await fetch(
          `${API_BASE}/api/shop-availability-rules`,
          {
            method: "POST",
            headers: {
              "Content-Type":
                "application/json",
            },
            body: JSON.stringify({
              shop_slug: shopSlug,
              weekday: day.weekday,
              start_time: `${day.start}:00`,
              end_time: `${day.end}:00`,
            }),
          }
        );

        if (!response.ok) {
          const error = await response
            .json()
            .catch(() => ({}));

          throw new Error(
            error.detail ||
              `Could not save ${day.name}.`
          );
        }
      }

      setMessage("Shop hours saved.");

      /*
       * Step 2 will be Staff.
       * For now we send them to the existing
       * Staff & Services page so the flow
       * already continues somewhere useful.
       */
      router.push(
        `/${shopSlug}/admin/staff`
      );
    } catch (error) {
      console.error(error);

      /*
       * Reload because some deletions or
       * additions may have completed before
       * an error occurred.
       */
      await loadHours();

      setMessage(
        error instanceof Error
          ? error.message
          : "Could not save your shop hours."
      );
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <main className={styles.page}>
        <div className={styles.loading}>
          Loading your setup...
        </div>
      </main>
    );
  }

  return (
    <main className={styles.page}>
      <div className={styles.container}>
        <header className={styles.header}>
          <div>
            <p className={styles.eyebrow}>
              LET&apos;S GET YOU READY
            </p>

            <h1 className={styles.title}>
              Set up your business
            </h1>

            <p className={styles.subtitle}>
              We&apos;ll walk you through
              everything. It only takes a few
              minutes.
            </p>
          </div>

          <div className={styles.stepBadge}>
            Step 1 of 5
          </div>
        </header>

        <section className={styles.progressCard}>
          <div
            className={`${styles.progressStep} ${styles.progressActive}`}
          >
            <span>1</span>
            <strong>Hours</strong>
          </div>

          <div className={styles.progressLine} />

          <div className={styles.progressStep}>
            <span>2</span>
            <strong>Staff</strong>
          </div>

          <div className={styles.progressLine} />

          <div className={styles.progressStep}>
            <span>3</span>
            <strong>Services</strong>
          </div>

          <div className={styles.progressLine} />

          <div className={styles.progressStep}>
            <span>4</span>
            <strong>Schedules</strong>
          </div>

          <div className={styles.progressLine} />

          <div className={styles.progressStep}>
            <span>5</span>
            <strong>Review</strong>
          </div>
        </section>

        <section className={styles.mainCard}>
          <div className={styles.cardHeading}>
            <div className={styles.icon}>
              🕒
            </div>

            <div>
              <p className={styles.stepLabel}>
                STEP 1
              </p>

              <h2 className={styles.cardTitle}>
                When is your business open?
              </h2>

              <p className={styles.cardText}>
                Choose your normal weekly
                hours. You can always change
                them later.
              </p>
            </div>
          </div>

          {message ? (
            <div className={styles.message}>
              {message}
            </div>
          ) : null}

          <div className={styles.days}>
            {hours.map((day) => (
              <div
                key={day.weekday}
                className={`${styles.dayCard} ${
                  day.open
                    ? styles.dayOpen
                    : styles.dayClosed
                }`}
              >
                <div className={styles.dayTop}>
                  <div>
                    <strong
                      className={styles.dayName}
                    >
                      {day.name}
                    </strong>

                    <p
                      className={
                        day.open
                          ? styles.openText
                          : styles.closedText
                      }
                    >
                      {day.open
                        ? "Open"
                        : "Closed"}
                    </p>
                  </div>

                  <label
                    className={styles.switch}
                  >
                    <input
                      type="checkbox"
                      checked={day.open}
                      onChange={(event) =>
                        updateDay(
                          day.weekday,
                          "open",
                          event.target.checked
                        )
                      }
                    />

                    <span
                      className={
                        styles.slider
                      }
                    />
                  </label>
                </div>

                {day.open ? (
                  <div
                    className={
                      styles.timeGrid
                    }
                  >
                    <label>
                      <span>Opens</span>

                      <input
                        type="time"
                        value={day.start}
                        onChange={(event) =>
                          updateDay(
                            day.weekday,
                            "start",
                            event.target.value
                          )
                        }
                      />
                    </label>

                    <label>
                      <span>Closes</span>

                      <input
                        type="time"
                        value={day.end}
                        onChange={(event) =>
                          updateDay(
                            day.weekday,
                            "end",
                            event.target.value
                          )
                        }
                      />
                    </label>
                  </div>
                ) : (
                  <div
                    className={
                      styles.closedMessage
                    }
                  >
                    No appointments will be
                    offered on {day.name}.
                  </div>
                )}
              </div>
            ))}
          </div>

          <div className={styles.footer}>
            <div>
              <strong>
                {openDayCount} days open
              </strong>

              <p>
                These become your normal shop
                hours.
              </p>
            </div>

            <button
              type="button"
              onClick={saveHours}
              disabled={saving}
              className={styles.continueButton}
            >
              {saving
                ? "Saving..."
                : "Save & Continue →"}
            </button>
          </div>
        </section>

        <p className={styles.helpText}>
          Don&apos;t worry — everything here can
          be changed later from Shop Setup.
        </p>
      </div>
    </main>
  );
}
