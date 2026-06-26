/**
 * AppEditForm — formulaire d'édition d'une application.
 * Utilisé à la fois dans la Modal (ManageApplications) et dans le Drawer (AppDrawerContent).
 *
 * Props :
 *   appId      {number|null}  — null = création, number = modification
 *   initial    {object}       — valeurs initiales du formulaire
 *   onSaved    {fn(app)}      — callback après sauvegarde réussie
 *   onCancel   {fn}           — callback annulation
 */
import { useState } from "react";
import { api, ENUMS } from "../api/client";
import { Field, Input, NumberInput, Select, Textarea } from "./Form";
import { CpePicker } from "./CpePicker";
import { useToast } from "../lib/useToast";

const EMPTY = {
  name: "", description: "", owner: "", team: "", email: "", phone: "",
  exposure: "Interne", technologies: "", technologies_cpe: "", url: "",
  scope_red_team: "", scope_pentest: "",
  dic_availability: 3, dic_integrity: 3, dic_confidentiality: 3,
};

export function AppEditForm({ appId, initial, onSaved, onCancel }) {
  const [form, setForm] = useState({ ...EMPTY, ...initial });
  const [err,  setErr]  = useState(null);
  const [busy, setBusy] = useState(false);
  const { show, node }  = useToast();

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  async function save() {
    if (!form.name.trim()) { setErr("Le nom est obligatoire."); return; }
    setBusy(true); setErr(null);
    try {
      let saved;
      if (appId) {
        saved = await api.updateApplication(appId, form);
        show("Application mise à jour");
      } else {
        saved = await api.createApplication(form);
        show("Application créée");
      }
      onSaved(saved ?? form);
    } catch (e) {
      setErr(e.message || "Erreur serveur");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>

      {/* Erreur */}
      {err && (
        <div style={{
          margin: "0 0 12px", padding: "9px 14px", borderRadius: 8,
          background: "rgba(226,75,74,.12)", border: "0.5px solid rgba(226,75,74,.4)",
          color: "#F09595", fontSize: 13,
        }}>{err}</div>
      )}

      <Field label="Nom *">
        <Input value={form.name} onChange={v => set("name", v)} placeholder="ex. CRM Clients" />
      </Field>

      <Field label="Description">
        <Textarea value={form.description} onChange={v => set("description", v)} />
      </Field>

      <div className="field-row">
        <Field label="Responsable"><Input value={form.owner} onChange={v => set("owner", v)} /></Field>
        <Field label="Équipe"><Input value={form.team}  onChange={v => set("team",  v)} /></Field>
      </div>

      <div className="field-row">
        <Field label="Email"><Input value={form.email} onChange={v => set("email", v)} /></Field>
        <Field label="Téléphone"><Input value={form.phone} onChange={v => set("phone", v)} /></Field>
      </div>

      <div className="field-row">
        <Field label="Exposition">
          <Select value={form.exposure} onChange={v => set("exposure", v)} options={ENUMS.exposure} />
        </Field>
        <Field label="URL">
          <Input value={form.url} onChange={v => set("url", v)} placeholder="https://…" />
        </Field>
      </div>

      <Field label="Technologies">
        <CpePicker
          valueRaw={form.technologies_cpe}
          onChange={(raw, readable) => setForm(f => ({ ...f, technologies_cpe: raw, technologies: readable }))}
        />
      </Field>

      <Field label="Criticité DIC (1 à 5)">
        <div className="field-row-3">
          <div>
            <span className="hint">Disponibilité</span>
            <NumberInput min={1} max={5} value={form.dic_availability} onChange={v => set("dic_availability", v)} />
          </div>
          <div>
            <span className="hint">Intégrité</span>
            <NumberInput min={1} max={5} value={form.dic_integrity} onChange={v => set("dic_integrity", v)} />
          </div>
          <div>
            <span className="hint">Confidentialité</span>
            <NumberInput min={1} max={5} value={form.dic_confidentiality} onChange={v => set("dic_confidentiality", v)} />
          </div>
        </div>
      </Field>

      <div className="field-row">
        <Field label="Scope Red Team">
          <Textarea value={form.scope_red_team} onChange={v => set("scope_red_team", v)} />
        </Field>
        <Field label="Scope Pentest">
          <Textarea value={form.scope_pentest}  onChange={v => set("scope_pentest",  v)} />
        </Field>
      </div>

      {/* Actions */}
      <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 8, paddingTop: 16, borderTop: "0.5px solid var(--line)" }}>
        <button className="btn btn-ghost" onClick={onCancel} disabled={busy}>Annuler</button>
        <button className="btn btn-primary" onClick={save} disabled={busy}>
          {busy ? "Enregistrement…" : "Enregistrer"}
        </button>
      </div>

      {node}
    </div>
  );
}
