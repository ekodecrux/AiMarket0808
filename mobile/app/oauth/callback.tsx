import { useRouter } from "expo-router";
import { Text, View } from "react-native";

import { Button, Card, c, Title } from "@/components/nexus";
import { ScreenContainer } from "@/components/screen-container";

/**
 * Provider consent is completed by the production backend callback. This route
 * intentionally never receives, logs, or stores OAuth codes, social tokens, or
 * template-auth sessions on the device.
 */
export default function OAuthCallback() {
  const router = useRouter();
  return (
    <ScreenContainer>
      <View style={{ margin: 18, marginTop: 42 }}>
        <Card>
          <Title eyebrow="Official provider consent" title="Return to Platform Hub" detail="The connection result is stored securely by the server. Refresh Platform Hub to view its status." />
          <Text style={{ color: c.muted, fontSize: 13, lineHeight: 19, marginBottom: 16 }}>AiMarket never receives or stores your social password, 2FA code, browser cookie, or provider access token on this device.</Text>
          <Button label="Open Platform Hub" icon="hub" onPress={() => router.replace("/platforms" as never)} />
        </Card>
      </View>
    </ScreenContainer>
  );
}
