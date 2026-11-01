import hr from "../i18n/hr.json";

const REPO = "https://github.com/dlukas99/klimakompas-hr";

export function AboutPage() {
  const { about } = hr;
  return (
    <div className="mx-auto max-w-3xl space-y-5 px-4 py-6">
      <div>
        <h1 className="text-2xl font-bold">{about.title}</h1>
        <p className="mt-2">{about.intro}</p>
      </div>
      <section>
        <h2 className="text-xl font-semibold">{about.methodTitle}</h2>
        <ol className="mt-1 list-decimal space-y-1 pl-5">
          {about.method.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ol>
      </section>
      <section>
        <h2 className="text-xl font-semibold">{about.limitsTitle}</h2>
        <ul className="mt-1 list-disc space-y-1 pl-5">
          {about.limits.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </section>
      <section>
        <h2 className="text-xl font-semibold">{about.disclaimerTitle}</h2>
        <p className="mt-1">{hr.app.disclaimer}</p>
      </section>
      <section>
        <h2 className="text-xl font-semibold">{about.privacyTitle}</h2>
        <p className="mt-1">{about.privacy}</p>
      </section>
      <section>
        <h2 className="text-xl font-semibold">{about.accessibilityTitle}</h2>
        <p className="mt-1">{about.accessibility}</p>
      </section>
      <section>
        <h2 className="text-xl font-semibold">{about.teamTitle}</h2>
        <p className="mt-1">{about.team}</p>
      </section>
      <section>
        <h2 className="text-xl font-semibold">{about.licensesTitle}</h2>
        <p className="mt-1">{about.licenses}</p>
        <p className="mt-1">
          <a href={REPO} className="underline">
            {about.repo}
          </a>
        </p>
      </section>
      <section>
        <h2 className="text-xl font-semibold">{about.aiTitle}</h2>
        <p className="mt-1">{about.ai}</p>
      </section>
    </div>
  );
}
