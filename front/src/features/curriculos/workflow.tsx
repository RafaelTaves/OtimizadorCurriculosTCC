import { ArrowRight, Check } from "lucide-react";
const steps = [
  { title: "Enviar", text: "Currículo e descrição da vaga." },
  { title: "Revisar", text: "Confira e confirme o texto extraído." },
  { title: "Otimizar", text: "Autorize o envio à IA e revise a proposta." },
  { title: "Editar", text: "Ajuste o LaTeX e gere seu PDF." },
];
export function Workflow() {
  return (
    <section className="workflow" aria-labelledby="fluxo-titulo">
      <h2 id="fluxo-titulo">Da sua experiência ao currículo</h2>
      <ol>
        {steps.map((step, index) => (
          <li key={step.title}>
            <div>
              <h3>{step.title}</h3>
              {index < steps.length - 1 && (
                <ArrowRight size={16} aria-hidden="true" />
              )}
            </div>
            <p>{step.text}</p>
          </li>
        ))}
      </ol>
      <p className="workflow-note">
        <Check size={16} aria-hidden="true" />O texto só será enviado à OpenAI
        depois da sua revisão e do seu consentimento.
      </p>
    </section>
  );
}
