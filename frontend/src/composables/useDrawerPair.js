import { computed, inject, onUnmounted, provide, ref } from 'vue'

// Appairage de tiroirs — panneaux côte à côte au lieu de la superposition par défaut.
//
// Un tiroir « hôte » (aujourd'hui RessourceDrawer) appelle provideDrawerPair() ; les
// DetailDrawer montés dans SA descendance de composants s'y enregistrent et reçoivent un
// index réactif. `teleport` déplace le DOM, pas la hiérarchie de composants : un tiroir
// compagnon monté en frère après </DetailDrawer> reste un descendant de l'hôte, donc
// l'injection le traverse sans rien changer aux composants compagnons eux-mêmes.
//
// Index 0 = hôte (collé à droite) · 1 = compagnon (décalé à gauche) · ≥ 2 = 3ᵉ niveau,
// qui retombe volontairement sur la superposition historique (article corpus, EntityForm…).
//
// Hors d'un hôte, useDrawerSlot() renvoie null : les ~8 autres sites d'appel de DetailDrawer
// gardent exactement le comportement actuel.
const KEY = Symbol('drawer-pair')

export function provideDrawerPair() {
  // Jetons des tiroirs enregistrés, dans l'ordre de montage.
  const slots = ref([])
  const registry = {
    register(token) {
      slots.value = [...slots.value, token]
      return computed(() => slots.value.indexOf(token))
    },
    unregister(token) {
      slots.value = slots.value.filter((t) => t !== token)
    },
    count: computed(() => slots.value.length),
  }
  provide(KEY, registry)
  return registry
}

// Appelé par DetailDrawer. Renvoie null hors appairage, sinon { index, count } réactifs.
export function useDrawerSlot() {
  const registry = inject(KEY, null)
  if (!registry) return null
  const token = Symbol('drawer-slot')
  const index = registry.register(token)
  onUnmounted(() => registry.unregister(token))
  return { index, count: registry.count }
}
