import {
  FiActivity,
  FiClock,
  FiCpu,
  FiZap,
} from "react-icons/fi";

import "./InferencePerformance.css";


function seconds(
  milliseconds
) {
  if (
    milliseconds === null ||
    milliseconds === undefined
  ) {
    return "—";
  }

  return (
    `${(
      milliseconds / 1000
    ).toFixed(2)} s`
  );
}


function rate(
  value
) {
  if (
    value === null ||
    value === undefined
  ) {
    return "—";
  }

  return (
    `${Number(value).toFixed(2)} tok/s`
  );
}


function Metric({
  icon: Icon,
  label,
  value,
  hint,
}) {
  return (
    <div className="aiw-perf-metric">

      <div className="aiw-perf-icon">
        <Icon />
      </div>

      <div>

        <span>
          {label}
        </span>

        <strong>
          {value}
        </strong>

        {hint && (
          <small>
            {hint}
          </small>
        )}

      </div>

    </div>
  );
}


export default function InferencePerformance({
  usage,
}) {
  if (
    !usage ||
    usage.latencyMs == null
  ) {
    return null;
  }


  return (
    <section className="aiw-performance">

      <div className="aiw-performance-header">

        <div>

          <FiActivity />

          <strong>
            Inference performance
          </strong>

        </div>

        <span>
          {
            usage.runtime ||
            "runtime"
          }
        </span>

      </div>


      <div className="aiw-performance-grid">

        <Metric
          icon={FiZap}
          label="TTFT"
          value={
            seconds(
              usage.ttftMs
            )
          }
          hint="Time to first token"
        />


        <Metric
          icon={FiClock}
          label="Total latency"
          value={
            seconds(
              usage.latencyMs
            )
          }
          hint="End-to-end request"
        />


        <Metric
          icon={FiClock}
          label="Generation time"
          value={
            seconds(
              usage
                .generationDurationMs
            )
          }
          hint="After first token"
        />


        <Metric
          icon={FiCpu}
          label="Completion tokens"
          value={
            usage
              .completionTokens ??
            "—"
          }
          hint="Generated output"
        />


        <Metric
          icon={FiZap}
          label="Generation rate"
          value={
            rate(
              usage
                .generationTokensPerSecond
            )
          }
          hint="Pure decoding throughput"
        />


        <Metric
          icon={FiActivity}
          label="End-to-end rate"
          value={
            rate(
              usage
                .outputTokensPerSecond
            )
          }
          hint="Includes TTFT"
        />

      </div>

    </section>
  );
}
