package com.tduck.companion

/** Providers produce display text and optional intents, never transport calls or motor values. */
data class AssistantReply(val text: String, val suggestedCommand: String? = null)
interface AssistantProvider { fun reply(text: String, battery: Int): AssistantReply }
class LocalDemoAssistant : AssistantProvider {
 override fun reply(text: String, battery: Int): AssistantReply {
  val intent = CommandPolicy.interpret(text)
  return when {
   intent != null -> AssistantReply("I understood '$intent'. Use the matching Control button to confirm. I never move from chat alone.", intent)
   "battery" in text.lowercase() -> AssistantReply("My simulated battery is $battery%.")
   else -> AssistantReply("Quack! I'm a local simulated assistant. Try asking about my battery or saying 'walk forward'.")
  }
 }
}
