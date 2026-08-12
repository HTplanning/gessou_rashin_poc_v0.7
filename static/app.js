/* 月相羅針 計算PoC v0.7｜Vue.js画面版
 *
 * Vue.js is responsible only for input state, API communication, errors,
 * loading state, and result rendering. Astronomical calculation and
 * classification remain in Flask/Python.
 */

(() => {
  "use strict";

  const pad2 = (value) => String(value).padStart(2, "0");

  const localCurrentDate = () => {
    const now = new Date();
    return [
      now.getFullYear(),
      pad2(now.getMonth() + 1),
      pad2(now.getDate()),
    ].join("-");
  };

  const localCurrentTime = () => {
    const now = new Date();
    return `${pad2(now.getHours())}:${pad2(now.getMinutes())}`;
  };

  const app = Vue.createApp({
    data() {
      return {
        form: {
          birth_date: "",
          birth_time: "",
          birth_place: "",
        },
        errors: [],
        loading: false,
        result: null,
      };
    },

    methods: {
      primeCurrentDateIfEmpty(event) {
        if (this.form.birth_date || event.currentTarget.value) return;

        // v0.6 behavior retained: when an empty native date picker opens,
        // use the device-local current date as the picker's current value.
        const value = localCurrentDate();
        event.currentTarget.value = value;
        this.form.birth_date = value;
      },

      primeCurrentTimeIfEmpty(event) {
        if (this.form.birth_time || event.currentTarget.value) return;

        // v0.6 behavior retained: when an empty native time picker opens,
        // use the device-local current time (minute precision).
        const value = localCurrentTime();
        event.currentTarget.value = value;
        this.form.birth_time = value;
      },

      resetForm() {
        // v0.5/v0.6 behavior retained: reset means truly empty, never the
        // previous calculation values. Current date/time are primed only when
        // the corresponding empty native picker is opened again.
        this.$nextTick(() => {
          this.form.birth_date = "";
          this.form.birth_time = "";
          this.form.birth_place = "";
          this.errors = [];
          this.result = null;
        });
      },

      async calculate() {
        if (this.loading) return;

        this.loading = true;
        this.errors = [];
        this.result = null;

        try {
          const response = await fetch("/api/calculate", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "Accept": "application/json",
            },
            body: JSON.stringify({
              birth_date: this.form.birth_date,
              birth_time: this.form.birth_time,
              birth_place: this.form.birth_place,
            }),
          });

          const data = await response.json();

          if (!response.ok || !data.success) {
            this.errors = Array.isArray(data.errors) && data.errors.length
              ? data.errors
              : ["計算中にエラーが発生しました。もう一度お試しください。"];
            return;
          }

          this.result = data.result;
        } catch (error) {
          console.error("月相羅針 API error", error);
          this.errors = [
            "通信または計算処理でエラーが発生しました。もう一度お試しください。",
          ];
        } finally {
          this.loading = false;
        }
      },

      formatNumber(value) {
        const number = Number(value);
        return Number.isFinite(number) ? number.toFixed(8) : "";
      },

      formatDegrees(value) {
        const formatted = this.formatNumber(value);
        return formatted ? `${formatted}°` : "";
      },

      phaseTitle(result) {
        return `${result.phase_id}｜${result.phase_name}`;
      },

      phaseNameWithEnglish(result) {
        return `${result.phase_name}（${result.phase_english_name}）`;
      },

      candidateLabel(index, count) {
        return count > 1 ? `候補${index + 1}` : "候補";
      },

      unknownTimeSamplingText(result) {
        return `${result.sample_interval_minutes}分刻み＋23:59:59を確認（45°区分の通過をサンプル間でも追跡）`;
      },
    },
  });

  app.mount("#app");
})();
