export default function PasswordStrengthMeter({ password }: { password: string }) {
  const score =
    (password.length >= 8 ? 1 : 0) +
    (password.length >= 12 ? 1 : 0) +
    (/[A-Z]/.test(password) ? 1 : 0) +
    (/[a-z]/.test(password) ? 1 : 0) +
    (/[0-9]/.test(password) ? 1 : 0) +
    (/[^A-Za-z0-9]/.test(password) ? 1 : 0);

  const colors = [
    "bg-rose-500",
    "bg-orange-500",
    "bg-yellow-500",
    "bg-lime-500",
    "bg-emerald-500",
    "bg-emerald-400",
  ];
  const labels = [
    "Very weak",
    "Weak",
    "Fair",
    "Good",
    "Strong",
    "Very strong",
  ];

  return (
    <div
      className="mt-1.5"
      role="progressbar"
      aria-valuenow={Math.min(100, (score / 6) * 100)}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={`Password strength: ${labels[Math.min(score, 5)]}`}
    >
      <div className="flex gap-1">
        {[0, 1, 2, 3, 4, 5].map((index) => (
          <div
            key={index}
            className={`h-1 flex-1 rounded-full transition-colors ${
              index < score ? colors[index] : "bg-white/[0.08]"
            }`}
          />
        ))}
      </div>
      <p className="mt-0.5 text-[10px] text-gray-500">
        {labels[Math.min(score, 5)]}
      </p>
    </div>
  );
}
