import * as Dialog from "radix-ui/dialog";
import type { ReactNode } from "react";
import identityCopy from "../../identity/copy.zh-CN.json";

export type IdentityCopy = typeof identityCopy;

export function IdentityHelp({ copy }: { copy: IdentityCopy }) {
  return (
    <Dialog.Root>
      <Dialog.Trigger asChild>
        <button type="button" className="oc-help">
          {copy.helpAction}
        </button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="oc-help-overlay" />
        <Dialog.Content className="oc-help-dialog">
          <Dialog.Title>{copy.helpTitle}</Dialog.Title>
          <Dialog.Description>{copy.helpDescription}</Dialog.Description>
          <Dialog.Close asChild>
            <button type="button">{copy.helpClose}</button>
          </Dialog.Close>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

export function IdentityLayout({
  copy,
  children,
  state = false,
}: {
  copy: IdentityCopy;
  children: ReactNode;
  state?: boolean;
}) {
  return (
    <div className={`oc-identity${state ? " oc-state" : ""}`}>
      <header className="oc-header">
        <div className="oc-brand">
          <span className="oc-mark" aria-hidden="true" />
          <span className="oc-name">{copy.brand}</span>
          <span className="oc-en">{copy.name}</span>
        </div>
        <span className="oc-language">{copy.language}</span>
      </header>
      <main className="oc-hero">
        <div className="oc-hero-inner">
          <section className="oc-intro" aria-label={copy.eyebrow}>
            <p className="oc-eyebrow">{copy.eyebrow}</p>
            <h1 className="oc-headline">
              {copy.headline[0]}
              <br />
              {copy.headline[1]}
            </h1>
            <p className="oc-description">
              {copy.description[0]}
              <br />
              {copy.description[1]}
            </p>
            <div className="oc-principles">
              {copy.principles.map((text) => (
                <span key={text}>{text}</span>
              ))}
            </div>
          </section>
          <section className="oc-card" aria-label={copy.cardLabel}>
            {children}
          </section>
        </div>
      </main>
      <section className="oc-features" aria-label="产品价值">
        <div className="oc-features-inner">
          {copy.features.map((feature) => (
            <article className="oc-feature" key={feature.icon}>
              <span
                className={`oc-feature-icon oc-feature-icon--${feature.icon}`}
                aria-hidden="true"
              />
              <div>
                <h3>{feature.title}</h3>
                <p>{feature.description}</p>
              </div>
            </article>
          ))}
        </div>
      </section>
      <footer className="oc-footer">
        <span>{copy.footer}</span>
        <span>{copy.assurance}</span>
      </footer>
    </div>
  );
}
