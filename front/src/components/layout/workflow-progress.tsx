import { Check } from "lucide-react";

const steps = ["Upload", "Revisão", "Otimização", "Editor"];

export function WorkflowProgress({ current }: { current: 0 | 1 | 2 | 3 }) {
  return (
    <nav aria-label="Etapas do currículo" className="workflow-progress">
      <ol>
        {steps.map((label, index) => (
          <li
            key={label}
            className={index < current ? "is-complete" : undefined}
            aria-current={index === current ? "step" : undefined}
          >
            <span className="step-marker" aria-hidden="true">
              {index < current ? <Check size={16} /> : index + 1}
            </span>
            <span>
              {label}
              <small>
                {index < current
                  ? "Concluída"
                  : index === current
                    ? "Etapa atual"
                    : "A seguir"}
              </small>
            </span>
          </li>
        ))}
      </ol>
    </nav>
  );
}
