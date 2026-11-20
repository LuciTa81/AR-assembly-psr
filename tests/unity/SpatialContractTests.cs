using System.IO;
using System.Text.Json;
using ARAssembly;
using NUnit.Framework;

public class SpatialContractTests
{
    private static GuidanceSnapshot Frame()
    {
        using (var json = JsonDocument.Parse(File.ReadAllText(Path.Combine(
            TestContext.CurrentContext.TestDirectory, "spatial_guidance_v1.json"))))
            return JsonSerializer.Deserialize<GuidanceSnapshot>(json.RootElement.GetProperty("expected").GetRawText(),
                new JsonSerializerOptions { IncludeFields = true });
    }

    [Test]
    public void SharedPythonContractKeepsAsymmetricEyeCoordinatesAndPoseIdentity()
    {
        var frame = Frame();
        Assert.That(frame.spatial.schema_version, Is.EqualTo("beast_spatial_guidance_v1"));
        Assert.That(frame.spatial.left_pixel, Is.EqualTo(new[] {1008.0, 540.0}));
        Assert.That(frame.spatial.right_pixel, Is.EqualTo(new[] {908.8, 539.62}));
        Assert.That(frame.spatial.pose_frame_id, Is.EqualTo(7));
        Assert.That(frame.frame_id, Is.EqualTo(8));
        Assert.That(frame.spatial.pose_age_ms, Is.EqualTo(25));
        Assert.That(frame.spatial.pose_timestamp_ms, Is.EqualTo(1000));
        Assert.That(frame.spatial.calibration_status, Is.EqualTo("synthetic"));
        Assert.That(frame.spatial.display_alignment_verified, Is.False);
    }

    [Test]
    public void OptionalSpatialDoesNotAdvanceAssemblyOrOptInToTestRing()
    {
        var state = new GuidanceState();
        Assert.That(state.Apply(Frame(), 1, 1.01), Is.True);
        Assert.That(state.LastSnapshot.current_state, Is.EqualTo("S2"));
        Assert.That(state.LastSnapshot.next_action, Is.EqualTo("Fasten screw A"));
        Assert.That(state.ShowTestRing(1.02, false), Is.False);
        var withoutSpatial = Frame();
        withoutSpatial.spatial = null;
        withoutSpatial.frame_id++;
        Assert.That(state.Apply(withoutSpatial, 1.02, 1.03), Is.True);
        Assert.That(state.LastSnapshot.spatial, Is.Null);
    }

    [Test]
    public void MissingSpatialFieldsCannotDefaultToVisibleOrVerified()
    {
        var frame = JsonSerializer.Deserialize<GuidanceSnapshot>("{\"spatial\":{}}",
            new JsonSerializerOptions { IncludeFields = true });
        Assert.That(frame.spatial.target_visible, Is.False);
        Assert.That(frame.spatial.display_alignment_verified, Is.False);
        Assert.That(frame.spatial.pose_frame_id, Is.EqualTo(-1));
        Assert.That(frame.spatial.pose_age_ms, Is.EqualTo(-1));
        Assert.That(frame.spatial.left_pixel, Is.Null);
        Assert.That(frame.spatial.right_pixel, Is.Null);
    }
}
