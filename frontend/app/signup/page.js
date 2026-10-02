our
                        business name. You can change the URL
                        above if you prefer something different.
                      </p>
                    </div>
                  </div>
                </div>

                <div className={styles.field}>
                  <label
                    className={styles.label}
                    htmlFor="businessType"
                  >
                    Business Type
                  </label>

                  <select
                    id="businessType"
                    className={styles.select}
                    value={businessType}
                    onChange={(event) =>
                      setBusinessType(
                        event.target.value
                      )
                    }
                    disabled={loading}
                  >
                    <option value="service_business">
                      Other Service Business
                    </option>

                    <option value="barbershop">
                      Barbershop
                    </option>

                    <option value="hair_salon">
                      Hair Salon
                    </option>

                    <option value="nail_salon">
                      Nail Salon
                    </option>

                    <option value="massage">
                      Massage / Wellness
                    </option>

                    <option value="trainer">
                      Personal Training / Fitness
                    </option>
                  </select>
                </div>

                <div className={styles.field}>
                  <label
                    className={styles.label}
                    htmlFor="phone"
                  >
                    Business Phone
                  </label>

                  <input
                    id="phone"
                    className={styles.input}
                    type="tel"
                    autoComplete="tel"
                    inputMode="tel"
                    value={phone}
                    onChange={(event) =>
                      setPhone(event.target.value)
                    }
                    placeholder="240-555-1234"
                    disabled={loading}
                  />
                </div>
              </div>
            </section>

            <section className={styles.section}>
              <h2 className={styles.sectionTitle}>
                Your account
              </h2>

              <div className={styles.grid}>
                <div className={styles.fullWidth}>
                  <div className={styles.field}>
                    <label
                      className={styles.label}
                      htmlFor="ownerName"
                    >
                      Your Name
                    </label>

                    <input
                      id="ownerName"
                      className={styles.input}
                      type="text"
                      autoComplete="name"
                      value={ownerName}
                      onChange={(event) =>
                        setOwnerName(
                          event.target.value
                        )
                      }
                      placeholder="Mike Smith"
                      disabled={loading}
                      required
                    />
                  </div>
                </div>

                <div className={styles.fullWidth}>
                  <div className={styles.field}>
                    <label
                      className={styles.label}
                      htmlFor="email"
                    >
                      Email
                    </label>

                    <input
                      id="email"
                      className={styles.input}
                      type="email"
                      autoComplete="email"
                      inputMode="email"
                      autoCapitalize="none"
                      spellCheck="false"
                      value={email}
                      onChange={(event) =>
                        setEmail(
                          event.target.value
                        )
                      }
                      placeholder="you@example.com"
                      disabled={loading}
                      required
                    />
                  </div>
                </div>

                <div className={styles.field}>
                  <label
                    className={styles.label}

                    htmlFor="password"
                  >
                    Password
                  </label>

                  <input
                    id="password"
                    className={styles.input}
                    type="password"
                    autoComplete="new-password"
                    value={password}
                    onChange={(event) =>
                      setPassword(
                        event.target.value
                      )
                    }
                    placeholder="At least 8 characters"
                    disabled={loading}
                    required
                  />
                </div>

                <div className={styles.field}>
                  <label
                    className={styles.label}
                    htmlFor="confirmPassword"
                  >
                    Confirm Password
                  </label>

                  <input
                    id="confirmPassword"
                    className={styles.input}
                    type="password"
                    autoComplete="new-password"
                    value={confirmPassword}
                    onChange={(event) =>
                      setConfirmPassword(
                        event.target.value
                      )
                    }
                    placeholder="Enter password again"
                    disabled={loading}
                    required
                  />
                </div>
              </div>
            </section>

            <section className={styles.section}>
              <div
                style={{
                  marginBottom: "16px",
                }}
              >
                <h2 className={styles.sectionTitle}>
                  Choose your plan
                </h2>

                <p
                  style={{
                    color: "#64748b",
                    fontSize: "14px",
                    lineHeight: "1.5",
                    marginTop: "5px",
                  }}
                >
                  Both plans include your first 30 days
                  free. Choose what works best for your
                  business.
                </p>
              </div>

              <div
                style={{
                  display: "grid",
                  gridTemplateColumns:
                    "repeat(auto-fit, minmax(260px, 1fr))",
                  gap: "16px",
                  alignItems: "stretch",
                }}
              >
                <button
                  type="button"
                  onClick={() =>
                    setSelectedPlan("scheduling")
                  }
                  disabled={loading}
                  style={{
                    textAlign: "left",
                    padding: "20px",
                    borderRadius: "18px",
                    border:
                      selectedPlan === "scheduling"
                        ? "3px solid #4f46e5"
                        : "2px solid #cbd5e1",
                    background:
                      selectedPlan === "scheduling"
                        ? "#eef2ff"
                        : "#ffffff",
                    cursor: loading
                      ? "default"
                      : "pointer",
                    boxShadow:
                      selectedPlan === "scheduling"
                        ? "0 5px 18px rgba(79,70,229,0.12)"
                        : "none",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent:
                        "space-between",
                      alignItems: "flex-start",
                      gap: "12px",
                    }}
                  >
                    <div>
                      <div
                        style={{
                          fontSize: "21px",
                          fontWeight: "900",
                          color: "#0f172a",
                        }}
                      >
                        Business Management
                      </div>

                      <div
                        style={{
                          marginTop: "4px",
                          fontSize: "20px",
                          fontWeight: "900",
                          color: "#4f46e5",
                        }}
                      >
                        $49/month
                      </div>
                    </div>

                    <div
                      style={{
                        width: "22px",
                        height: "22px",
                        borderRadius: "50%",
                        border:
                          selectedPlan ===
                          "scheduling"
                            ? "6px solid #4f46e5"
                            : "2px solid #94a3b8",
                        background: "#ffffff",
                        flexShrink: 0,
                      }}
                    />
                  </div>

                  <p
                    style={{
                      marginTop: "14px",
                      marginBottom: "14px",
                      color: "#475569",
                      fontWeight: "700",
                      lineHeight: "1.5",
                    }}
                  >
                    Everything you need to manage your
                    appointments and customers.
                  </p>

                  <div
                    style={{
                      display: "grid",
                      gap: "8px",
                    }}
                  >
                    {businessFeatures.map(
                      (feature) => (
                        <div
                          key={feature}
                          style={{
                            display: "flex",
                            gap: "8px",
                            color: "#334155",
                            fontSize: "14px",
                            lineHeight: "1.4",
                          }}
                        >
                          <span
                            style={{
                              color: "#16a34a",
                              fontWeight: "900",
                            }}
                          >
                            ✓
                          </span>

                          <span>{feature}</span>
                        </div>
                      )
                    )}
                  </div>

                  <div
                    style={{
                      marginTop: "18px",
                      padding: "10px 12px",
                      borderRadius: "10px",
                      background: "#ffffff",
                      color: "#3730a3",
                      fontWeight: "800",
                      fontSize: "13px",
                    }}
                  >
                    Your first 30 days are free.
                  </div>
                </button>

                <button
                  type="button"
                  onClick={() =>
                    setSelectedPlan(
                      "scheduling_ai"
                    )
                  }
                  disabled={loading}
                  style={{
                    textAlign: "left",
                    padding: "20px",
                    borderRadius: "18px",
                    border:
                      selectedPlan ===
                      "scheduling_ai"
                        ? "3px solid #7c3aed"
                        : "2px solid #c4b5fd",
                    background:
                      selectedPlan ===
                      "scheduling_ai"
                        ? "#f5f3ff"
                        : "#fafaff",
                    cursor: loading
                      ? "default"
                      : "pointer",
                    boxShadow:
                      selectedPlan ===
                      "scheduling_ai"
                        ? "0 5px 18px rgba(124,58,237,0.14)"
                        : "none",
                  }}
                >
                  <div
                    style={{
                      display: "inline-block",
                      marginBottom: "12px",
                      padding: "6px 10px",
                      borderRadius: "999px",
                      background: "#7c3aed",
                      color: "#ffffff",
                      fontSize: "12px",
                      fontWeight: "900",
                    }}
                  >
                    NEVER MISS A CALL
                  </div>

                  <div
                    style={{
                      display: "flex",
                      justifyContent:
                        "space-between",
                      alignItems: "flex-start",
                      gap: "12px",
                    }}
                  >
                    <div>
                      <div
                        style={{
                          fontSize: "21px",
                          fontWeight: "900",
                          color: "#0f172a",
                        }}
                      >
                        Business Management
                        <br />
                        + AI Receptionist
                      </div>

                      <div
                        style={{
                          marginTop: "4px",
                          fontSize: "20px",
                          fontWeight: "900",
                          color: "#7c3aed",
                        }}
                      >
                        $198/month total
                      </div>

                      <div
                        style={{
                          marginTop: "3px",
                          color: "#64748b",
                          fontSize: "12px",
                          fontWeight: "700",
                        }}
                      >
                        Includes Business Management
                      </div>
                    </div>

                    <div
                      style={{
                        width: "22px",
                        height: "22px",
                        borderRadius: "50%",
                        border:
                          selectedPlan ===
                          "scheduling_ai"
                            ? "6px solid #7c3aed"
                            : "2px solid #94a3b8",
                        background: "#ffffff",
                        flexShrink: 0,
                      }}
                    />
                  </div>

                  <div
                    style={{
                      marginTop: "14px",
                      marginBottom: "14px",
                      padding: "12px",
                      borderRadius: "12px",
                      background: "#ede9fe",
                      color: "#5b21b6",
                      fontWeight: "900",
                      lineHeight: "1.45",
                    }}
                  >
                    Never lose a customer because you
                    couldn&apos;t answer the phone.
                  </div>

                  <p
                    style={{
                      color: "#475569",
                      fontWeight: "700",
                      lineHeight: "1.5",
                      marginBottom: "13px",
                    }}
                  >
                    Everything in Business Management,
                    plus:
                  </p>

                  <div
                    style={{
                      display: "grid",
                      gap: "8px",
                    }}
                  >
                    {aiFeatures.map((feature) => (
                      <div
                        key={feature}
                        style={{
                          display: "flex",
                          gap: "8px",
                          color: "#334155",
                          fontSize: "14px",
                          lineHeight: "1.4",
                        }}
                      >
                        <span
                          style={{
                            color: "#7c3aed",
                            fontWeight: "900",
                          }}
                        >
                          ✓
                        </span>

                        <span>{feature}</span>
                      </div>
                    ))}
                  </div>

                  <div
                    style={{
                      marginTop: "18px",
                      padding: "10px 12px",
                      borderRadius: "10px",
                      background: "#ffffff",
                      color: "#5b21b6",
                      fontWeight: "800",
                      fontSize: "13px",
                    }}
                  >
                    Your first 30 days are free.
                  </div>
                </button>
              </div>
            </section>

            <div
              style={{
                background: "#eef2ff",
                border: "1px solid #c7d2fe",
                borderRadius: "14px",
                padding: "16px",
                marginBottom: "16px",
                color: "#3730a3",
                fontSize: "14px",
                lineHeight: "1.55",
                fontWeight: "650",
              }}
            >
              <strong>
                Next: secure card setup with Stripe.
              </strong>
              <br />
              A credit card is required to start your
              free trial, but you&apos;ll pay{" "}
              <strong>$0 today</strong>. You won&apos;t
              be charged until your 30-day free trial
              ends.
              <br />
              <br />
              After 30 days, your selected plan will be{" "}
              <strong>
                {selectedPlan === "scheduling_ai"
                  ? "$198 per month"
                  : "$49 per month"}
              </strong>{" "}
              unless you cancel.
            </div>

            <button
              className={styles.button}
              type="submit"
              disabled={loading}
            >
              {loading
                ? "Opening Secure Checkout..."
                : "Create Account & Start Free Trial"}
            </button>
          </form>

          <p className={styles.footer}>
            Already have a ChairTime account?{" "}
            <Link
              href="/login"
              className={styles.loginLink}
            >
              Sign in
            </Link>
          </p>
        </section>
      </div>
    </main>
  );
}
