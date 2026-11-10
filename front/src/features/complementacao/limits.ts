// Tetos publicados pelo contrato atual; a API pode reduzir esses valores por instalação.
export const interviewPresentationLimits = {
  questionsPerRound: 3,
  maximumRounds: 2,
  answerCharacters: 4_000,
  complementItems: 24,
  complementCharacters: 12_000,
  totalConfirmedCharacters: 12_000,
} as const;
