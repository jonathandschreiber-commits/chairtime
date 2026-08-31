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

  const [currentStep, setCurrentStep] = useState(1);

  const [hours, setHours] = useState(
    makeDefaultHours()
  );

  const [existingRules, setExistingRules] =
    useState([]);

  const [staff, setStaff] = useState([]);
  const [services, setServices] = useState([]);

  const [newStaffName, setNewStaffName] =
    useState("");

  const [newServiceName, setNewServiceName] =
    useState("");

  const [loading, setLoading] = useState(true);

  const [savingHours, setSavingHours] =
    useState(false);

  const [addingStaff, setAddingStaff] =
    useState(false);

  const [addingService, setAddingService] =
    useState(false);

  const [message, setMessage] = useState("");

  const openDayCount = useMemo(() => {
    return hours.filter((day) => day.open).length;
  }, [hours]);

  useEffect(() => {
    if (!shopSlug) return;

    loadOnboardingData();
  }, [shopSlug]);

  async function loadOnboardingData() {
    setLoading(true);
    setMessage("");

    try {
      const query =
        "?shop_slug=" +
        encodeURIComponent(shopSlug);

      const [
        hoursResponse,
        staffResponse,
        servicesResponse,
      ] = await Promise.all([
        fetch(
          `${API_BASE}/api/shop-availability-rules${query}`,
          {
            cache: "no-store",
          }
        ),
        fetch(
          `${API_BASE}/api/barbers${query}`,
          {
            cache: "no-store",
          }
        ),
        fetch(
          `${API_BASE}/api/service-catalog${query}`,
          {
            cache: "no-store",
          }
        ),
      ]);

      if (!hoursResponse.ok) {
        throw new Error(
          "Could not load your shop hours."
        );
      }

      if (!staffResponse.ok) {
        throw new Error(
          "Could not load your staff."
        );
      }

      if (!servicesResponse.ok) {
        throw new Error(
          "Could not load your services."
        );
      }

      const hoursData =
        await hoursResponse.json();

      const staffData =
        await staffResponse.json();

      const servicesData =
        await servicesResponse.json();

      setExistingRules(hoursData);
      setStaff(staffData);
      setServices(servicesData);

      if (hoursData.length > 0) {
        setHours(
          DAYS.map((day) => {
            const rule = hoursData.find(
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

      /*
       * Resume onboarding automatically.
       */
      if (hoursData.length === 0) {
        setCurrentStep(1);
      } else if (staffData.length === 0) {
        setCurrentStep(2);
      } else if (servicesData.length === 0) {
        setCurrentStep(3);
      } else {
        setCurrentStep(4);
      }
    } catch (error) {
      console.error(error);

      setMessage(
        error instanceof Error
          ? error.message
          : "Could not load your setup."
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
    if (savingHours) return;

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

    setSavingHours(true);
    setMessage("");

    try {
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
            typeof error.detail === "string"
              ? error.detail
              : `Could not save ${day.name}.`
          );
        }
      }

      const refreshedResponse =
        await fetch(
          `${API_BASE}/api/shop-availability-rules?shop_slug=${encodeURIComponent(
            shopSlug
          )}`,
          {
            cache: "no-store",
          }
        );

      if (refreshedResponse.ok) {
        setExistingRules(
          await refreshedResponse.json()
        );
      }

      setMessage("");
      setCurrentStep(2);
    } catch (error) {
      console.error(error);

      setMessage(
        error instanceof Error
          ? error.message
          : "Could not save your shop hours."
      );
    } finally {
      setSavingHours(false);
    }
  }

  async function addStaffMember(event) {
    event?.preventDefault();

    if (addingStaff) return;

    const cleanName =
      newStaffName.trim();

    if (!cleanName) {
      setMessage(
        "Enter the staff member's name."
      );

      return;
    }

    setAddingStaff(true);
    setMessage("");

    try {
      const existingStaff =
        staff[0];

      const response = await fetch(
        `${API_BASE}/api/barbers`,
        {
          method: "POST",
          headers: {
            "Content-Type":
              "application/json",
          },
          body: JSON.stringify({
            name: cleanName,
            shop_name:
              existingStaff?.shop_name ||
              shopSlug,
            phone: "",
            timezone:
              existingStaff?.timezone ||
              "America/New_York",
            shop_slug: shopSlug,
          }),
        }
      );

      if (!response.ok) {
        const error = await response
          .json()
          .catch(() => ({}));

        throw new Error(
          typeof error.detail === "string"
            ? error.detail
            : "Could not add staff member."
        );
      }

      setNewStaffName("");

      await reloadStaff();

      setMessage(
        `${cleanName} added.`
      );
    } catch (error) {
      console.error(error);

      setMessage(
        error instanceof Error
          ? error.message
          : "Could not add staff member."
      );
    } finally {
      setAddingStaff(false);
    }
  }

  async function reloadStaff() {
    const response = await fetch(
      `${API_BASE}/api/barbers?shop_slug=${encodeURIComponent(
        shopSlug
      )}`,
      {
        cache: "no-store",
      }
    );

    if (!response.ok) {
      throw new Error(
        "Could not reload your staff."
      );
    }

    setStaff(
      await response.json()
    );
  }

  async function removeStaffMember(
    person
  ) {
    const confirmed = window.confirm(
      `Remove ${person.name} from your staff?`
    );

    if (!confirmed) return;

    setMessage("");

    try {
      const response = await fetch(
        `${API_BASE}/api/barbers/${encodeURIComponent(
          person.id
        )}`,
        {
          method: "DELETE",
        }
      );

      if (!response.ok) {
        const error = await response
          .json()
          .catch(() => ({}));

        throw new Error(
          typeof error.detail === "string"
            ? error.detail
            : "Could not remove staff member."
        );
      }

      await reloadStaff();

      setMessage(
        `${person.name} removed.`
      );
    } catch (error) {
      console.error(error);

      setMessage(
        error instanceof Error
          ? error.message
          : "Could not remove staff member."
      );
    }
  }

  function continueFromStaff() {
    if (staff.length === 0) {
      setMessage(
        "Add at least one person who customers can book with."
      );

      return;
    }

    setMessage("");
    setCurrentStep(3);
  }

  async function addService(event) {
    event?.preventDefault();

    if (addingService) return;

    const cleanName =
      newServiceName.trim();

    if (!cleanName) {
      setMessage(
        "Enter a service name."
      );

      return;
    }

    setAddingService(true);
    setMessage("");

    try {
      const response = await fetch(
        `${API_BASE}/api/service-catalog`,
        {
          method: "POST",
          headers: {
            "Content-Type":
              "application/json",
          },
          body: JSON.stringify({
            shop_slug: shopSlug,
            name: cleanName,
          }),
        }
      );

      if (!response.ok) {
        const error = await response
          .json()
          .catch(() => ({}));

        throw new Error(
          typeof error.detail === "string"
            ? error.detail
            : "Could not add service."
        );
      }

      setNewServiceName("");

      await reloadServices();

      setMessage(
        `${cleanName} added.`
      );
    } catch (error) {
      console.error(error);

      setMessage(
        error instanceof Error
          ? error.message
          : "Could not add service."
      );
    } finally {
      setAddingService(false);
    }
  }

  async function reloadServices() {
    const response = await fetch(
      `${API_BASE}/api/service-catalog?shop_slug=${encodeURIComponent(
        shopSlug
      )}`,
      {
        cache: "no-store",
      }
    );

    if (!response.ok) {
      throw new Error(
        "Could not reload your services."
      );
    }

    setServices(
      await response.json()
    );
  }

  async function removeService(
    service
  ) {
    const confirmed = window.confirm(
      `Remove ${service.name} from your service list?`
    );

    if (!confirmed) return;

    setMessage("");

    try {
      const response = await fetch(
        `${API_BASE}/api/service-catalog/${encodeURIComponent(
          service.id
        )}`,
        {
          method: "DELETE",
        }
      );

      if (!response.ok) {
        const error = await response
          .json()
          .catch(() => ({}));

        if (
          error.detail &&
          typeof error.detail === "object"
        ) {
          const assignedStaff =
            error.detail.assigned_staff || [];

          if (
            assignedStaff.length > 0
          ) {
            throw new Error(
              `${service.name} is already assigned to ${assignedStaff.join(
                ", "
              )}.`
            );
          }
        }

        throw new Error(
          typeof error.detail === "string"
            ? error.detail
            : "Could not remove service."
        );
      }

      await reloadServices();

      setMessage(
        `${service.name} removed.`
      );
    } catch (error) {
      console.error(error);

      setMessage(
        error instanceof Error
          ? error.message
          : "Could not remove service."
      );
    }
  }

  function continueFromServices() {
    if (services.length === 0) {
      setMessage(
        "Add at least one service customers can book."
      );

      return;
    }

    setMessage("");
    setCurrentStep(4);
  }

  function goToStep(step) {
    setMessage("");
    setCurrentStep(step);
  }

  function openExistingScheduleSetup() {
    router.push(
      `/${shopSlug}/admin/setup`
    );
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
            Step {currentStep} of 5
          </div>
        </header>

        <Progress
          currentStep={currentStep}
        />

        {currentStep === 1 && (
          <HoursStep
            hours={hours}
            openDayCount={openDayCount}
            updateDay={updateDay}
            saveHours={saveHours}
            savingHours={savingHours}
            message={message}
          />
        )}

        {currentStep === 2 && (
          <StaffStep
            staff={staff}
            newStaffName={newStaffName}
            setNewStaffName={
              setNewStaffName
            }
            addingStaff={addingStaff}
            addStaffMember={addStaffMember}
            removeStaffMember={
              removeStaffMember
            }
            continueFromStaff={
              continueFromStaff
            }
            goBack={() =>
              goToStep(1)
            }
            message={message}
          />
        )}

        {currentStep === 3 && (
          <ServicesStep
            services={services}
            newServiceName={
              newServiceName
            }
            setNewServiceName={
              setNewServiceName
            }
            addingService={
              addingService
            }
            addService={addService}
            removeService={removeService}
            continueFromServices={
              continueFromServices
            }
            goBack={() =>
              goToStep(2)
            }
            message={message}
          />
        )}

        {currentStep === 4 && (
          <ScheduleBridge
            goBack={() =>
              goToStep(3)
            }
            openExistingScheduleSetup={
              openExistingScheduleSetup
            }
          />
        )}

        <p className={styles.helpText}>
          Don&apos;t worry — everything here
          can be changed later from your
          Admin pages.
        </p>
      </div>
    </main>
  );
}

function Progress({
  currentStep,
}) {
  const steps = [
    "Hours",
    "Staff",
    "Services",
    "Schedules",
    "Review",
  ];

  return (
    <section className={styles.progressCard}>
      {steps.map((label, index) => {
        const stepNumber = index + 1;

        const isActive =
          stepNumber === currentStep;

        const isDone =
          stepNumber < currentStep;

        return (
          <div
            key={label}
            className={
              styles.progressGroup
            }
          >
            <div
              className={[
                styles.progressStep,
                isActive
                  ? styles.progressActive
                  : "",
                isDone
                  ? styles.progressDone
                  : "",
              ]
                .filter(Boolean)
                .join(" ")}
            >
              <span>
                {isDone
                  ? "✓"
                  : stepNumber}
              </span>

              <strong>{label}</strong>
            </div>

            {index <
              steps.length - 1 && (
              <div
                className={[
                  styles.progressLine,
                  isDone
                    ? styles.progressLineDone
                    : "",
                ]
                  .filter(Boolean)
                  .join(" ")}
              />
            )}
          </div>
        );
      })}
    </section>
  );
}

function HoursStep({
  hours,
  openDayCount,
  updateDay,
  saveHours,
  savingHours,
  message,
}) {
  return (
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
            Choose your normal weekly hours.
            You can always change them later.
          </p>
        </div>
      </div>

      <Message message={message} />

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
          disabled={savingHours}
          className={
            styles.continueButton
          }
        >
          {savingHours
            ? "Saving..."
            : "Save & Continue →"}
        </button>
      </div>
    </section>
  );
}

function StaffStep({
  staff,
  newStaffName,
  setNewStaffName,
  addingStaff,
  addStaffMember,
  removeStaffMember,
  continueFromStaff,
  goBack,
  message,
}) {
  return (
    <section
      className={`${styles.mainCard} ${styles.staffCard}`}
    >
      <div className={styles.cardHeading}>
        <div
          className={`${styles.icon} ${styles.staffIcon}`}
        >
          👥
        </div>

        <div>
          <p
            className={`${styles.stepLabel} ${styles.staffStepLabel}`}
          >
            STEP 2
          </p>

          <h2 className={styles.cardTitle}>
            Who takes appointments?
          </h2>

          <p className={styles.cardText}>
            Add yourself and anyone else
            customers can book with.
          </p>
        </div>
      </div>

      <Message message={message} />

      <form
        className={
          styles.addPersonCard
        }
        onSubmit={addStaffMember}
      >
        <label
          className={styles.formLabel}
          htmlFor="staffName"
        >
          Staff member&apos;s name
        </label>

        <div className={styles.addRow}>
          <input
            id="staffName"
            type="text"
            value={newStaffName}
            onChange={(event) =>
              setNewStaffName(
                event.target.value
              )
            }
            placeholder="Example: Maria"
            className={styles.textInput}
            disabled={addingStaff}
          />

          <button
            type="submit"
            disabled={addingStaff}
            className={
              styles.staffAddButton
            }
          >
            {addingStaff
              ? "Adding..."
              : "+ Add Staff"}
          </button>
        </div>
      </form>

      <div className={styles.peopleList}>
        {staff.length === 0 ? (
          <div
            className={styles.emptyState}
          >
            <div
              className={
                styles.emptyIcon
              }
            >
              👋
            </div>

            <strong>
              Start with yourself
            </strong>

            <p>
              Add the first person customers
              can book with.
            </p>
          </div>
        ) : (
          staff.map((person) => (
            <div
              key={person.id}
              className={
                styles.personRow
              }
            >
              <div
                className={
                  styles.personAvatar
                }
              >
                {String(person.name)
                  .trim()
                  .slice(0, 1)
                  .toUpperCase()}
              </div>

              <div
                className={
                  styles.personInfo
                }
              >
                <strong>
                  {person.name}
                </strong>

                <span>
                  Ready for services and
                  schedule
                </span>
              </div>

              <div
                className={
                  styles.readyBadge
                }
              >
                ✓ Added
              </div>

              <button
                type="button"
                onClick={() =>
                  removeStaffMember(
                    person
                  )
                }
                className={
                  styles.removeButton
                }
              >
                Remove
              </button>
            </div>
          ))
        )}
      </div>

      <div className={styles.footer}>
        <button
          type="button"
          onClick={goBack}
          className={styles.backButton}
        >
          ← Back
        </button>

        <div
          className={
            styles.footerRight
          }
        >
          <div>
            <strong>
              {staff.length}{" "}
              {staff.length === 1
                ? "person"
                : "people"}{" "}
              added
            </strong>

            <p>
              You can add more staff later.
            </p>
          </div>

          <button
            type="button"
            onClick={
              continueFromStaff
            }
            className={
              styles.continueButton
            }
          >
            Continue to Services →
          </button>
        </div>
      </div>
    </section>
  );
}

function ServicesStep({
  services,
  newServiceName,
  setNewServiceName,
  addingService,
  addService,
  removeService,
  continueFromServices,
  goBack,
  message,
}) {
  return (
    <section
      className={`${styles.mainCard} ${styles.servicesCard}`}
    >
      <div className={styles.cardHeading}>
        <div
          className={`${styles.icon} ${styles.serviceIcon}`}
        >
          ✨
        </div>

        <div>
          <p
            className={`${styles.stepLabel} ${styles.serviceStepLabel}`}
          >
            STEP 3
          </p>

          <h2 className={styles.cardTitle}>
            What services do you offer?
          </h2>

          <p className={styles.cardText}>
            Add each service customers should
            be able to book. We&apos;ll connect
            them to staff in the next step.
          </p>
        </div>
      </div>

      <Message message={message} />

      <form
        className={
          styles.addServiceCard
        }
        onSubmit={addService}
      >
        <label
          className={styles.formLabel}
          htmlFor="serviceName"
        >
          Service name
        </label>

        <div className={styles.addRow}>
          <input
            id="serviceName"
            type="text"
            value={newServiceName}
            onChange={(event) =>
              setNewServiceName(
                event.target.value
              )
            }
            placeholder="Example: Haircut"
            className={styles.textInput}
            disabled={addingService}
          />

          <button
            type="submit"
            disabled={addingService}
            className={
              styles.serviceAddButton
            }
          >
            {addingService
              ? "Adding..."
              : "+ Add Service"}
          </button>
        </div>

        <div
          className={
            styles.serviceExamples
          }
        >
          Examples: Haircut, Color,
          Manicure, Massage, Personal
          Training
        </div>
      </form>

      <div
        className={styles.serviceList}
      >
        {services.length === 0 ? (
          <div
            className={styles.emptyState}
          >
            <div
              className={
                styles.emptyIcon
              }
            >
              ✨
            </div>

            <strong>
              Add your first service
            </strong>

            <p>
              Start with the service customers
              book most often.
            </p>
          </div>
        ) : (
          services.map((service) => (
            <div
              key={service.id}
              className={
                styles.serviceRow
              }
            >
              <div
                className={
                  styles.serviceMark
                }
              >
                ✓
              </div>

              <div
                className={
                  styles.personInfo
                }
              >
                <strong>
                  {service.name}
                </strong>

                <span>
                  Duration and price come next
                </span>
              </div>

              <button
                type="button"
                onClick={() =>
                  removeService(
                    service
                  )
                }
                className={
                  styles.removeButton
                }
              >
                Remove
              </button>
            </div>
          ))
        )}
      </div>

      <div className={styles.footer}>
        <button
          type="button"
          onClick={goBack}
          className={styles.backButton}
        >
          ← Back
        </button>

        <div
          className={
            styles.footerRight
          }
        >
          <div>
            <strong>
              {services.length}{" "}
              {services.length === 1
                ? "service"
                : "services"}{" "}
              added
            </strong>

            <p>
              You can change these later.
            </p>
          </div>

          <button
            type="button"
            onClick={
              continueFromServices
            }
            className={
              styles.continueButton
            }
          >
            Continue to Schedules →
          </button>
        </div>
      </div>
    </section>
  );
}

function ScheduleBridge({
  goBack,
  openExistingScheduleSetup,
}) {
  return (
    <section
      className={`${styles.mainCard} ${styles.scheduleCard}`}
    >
      <div className={styles.cardHeading}>
        <div
          className={`${styles.icon} ${styles.scheduleIcon}`}
        >
          📅
        </div>

        <div>
          <p
            className={`${styles.stepLabel} ${styles.scheduleStepLabel}`}
          >
            STEP 4
          </p>

          <h2 className={styles.cardTitle}>
            Set up each person&apos;s schedule
          </h2>

          <p className={styles.cardText}>
            Next we&apos;ll connect services,
            prices, durations, and working
            hours to each staff member.
          </p>
        </div>
      </div>

      <div
        className={
          styles.nextStepPanel
        }
      >
        <div
          className={
            styles.nextStepIcon
          }
        >
          ✓
        </div>

        <div>
          <strong>
            Hours, staff, and services are
            ready.
          </strong>

          <p>
            We&apos;re ready to configure the
            individual schedules.
          </p>
        </div>
      </div>

      <div className={styles.footer}>
        <button
          type="button"
          onClick={goBack}
          className={styles.backButton}
        >
          ← Back
        </button>

        <button
          type="button"
          onClick={
            openExistingScheduleSetup
          }
          className={
            styles.continueButton
          }
        >
          Continue to Schedule Setup →
        </button>
      </div>
    </section>
  );
}

function Message({
  message,
}) {
  if (!message) return null;

  return (
    <div className={styles.message}>
      {message}
    </div>
  );
}
